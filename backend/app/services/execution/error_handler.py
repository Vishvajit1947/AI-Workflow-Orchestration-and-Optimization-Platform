"""
Enhanced error handling for LLM calls: error classification, retries with
exponential backoff, per-attempt timeouts and a per-provider circuit breaker.
Model fallback is decided by the execution engine (via the router) when
ErrorHandler gives up on a model.
"""
import asyncio
import time
from typing import Awaitable, Callable, Optional

from backend.app.config import settings
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse

TRANSIENT = "transient"      # retry may succeed
RATE_LIMIT = "rate_limit"    # retry after a longer wait
PERMANENT = "permanent"      # retrying the same model is pointless

_RATE_LIMIT_NAMES = ("ratelimit", "resourceexhausted", "toomanyrequests")
_TRANSIENT_NAMES = ("timeout", "connection", "internalserver", "serviceunavailable", "overloaded", "apierror")
_PERMANENT_NAMES = ("authentication", "permissiondenied", "notfound", "badrequest", "unprocessable", "invalidargument")
_RATE_LIMIT_WORDS = ("rate limit", "rate_limit", "too many requests", "quota", "resource exhausted")
_PERMANENT_WORDS = ("api key", "unauthorized", "forbidden", "not registered", "does not exist", "model not found")


def _status_code(error: Exception) -> Optional[int]:
    code = getattr(error, "status_code", None) or getattr(getattr(error, "response", None), "status_code", None)
    return code if isinstance(code, int) else None


def classify_error(error: Exception) -> str:
    """Classify an LLM call error as TRANSIENT, RATE_LIMIT or PERMANENT."""
    code = _status_code(error)
    if code is not None:
        if code == 429:
            return RATE_LIMIT
        if code in (408, 409) or code >= 500:
            return TRANSIENT
        if 400 <= code < 500:
            return PERMANENT

    if isinstance(error, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
        return TRANSIENT

    name = type(error).__name__.lower()
    message = str(error).lower()
    if any(n in name for n in _RATE_LIMIT_NAMES) or any(w in message for w in _RATE_LIMIT_WORDS):
        return RATE_LIMIT
    if any(n in name for n in _PERMANENT_NAMES) or any(w in message for w in _PERMANENT_WORDS):
        return PERMANENT
    if any(n in name for n in _TRANSIENT_NAMES):
        return TRANSIENT
    return TRANSIENT  # unknown errors: assume a retry might help


class CircuitBreaker:
    """
    Per-provider circuit breaker.
    closed: calls allowed. After `failure_threshold` consecutive failures -> open.
    open: calls refused until `timeout` seconds pass -> half-open.
    half-open: one trial call allowed; success closes the circuit, failure re-opens it.
    """

    def __init__(self, failure_threshold: Optional[int] = None, timeout: Optional[float] = None,
                 clock: Callable[[], float] = time.monotonic):
        self.failure_threshold = failure_threshold or settings.CIRCUIT_BREAKER_THRESHOLD
        self.timeout = timeout if timeout is not None else settings.CIRCUIT_BREAKER_TIMEOUT
        self.clock = clock
        self.failures: dict[str, int] = {}
        self.opened_at: dict[str, float] = {}
        self.trial_in_flight: set[str] = set()

    def state(self, provider: str) -> str:
        if provider not in self.opened_at:
            return "closed"
        if self.clock() - self.opened_at[provider] >= self.timeout:
            return "half_open"
        return "open"

    def allow_request(self, provider: str) -> bool:
        """Whether a call to the provider may go ahead now (claims the half-open trial slot)."""
        state = self.state(provider)
        if state == "closed":
            return True
        if state == "half_open" and provider not in self.trial_in_flight:
            self.trial_in_flight.add(provider)
            return True
        return False

    def is_open(self, provider: str) -> bool:
        """True while calls to the provider should be avoided (open, or half-open with a trial running)."""
        state = self.state(provider)
        return state == "open" or (state == "half_open" and provider in self.trial_in_flight)

    def record_success(self, provider: str) -> None:
        self.failures.pop(provider, None)
        self.opened_at.pop(provider, None)
        self.trial_in_flight.discard(provider)

    def record_failure(self, provider: str) -> None:
        self.trial_in_flight.discard(provider)
        if provider in self.opened_at:
            # Failed half-open trial (or failure while open): restart the open period
            self.opened_at[provider] = self.clock()
            return
        self.failures[provider] = self.failures.get(provider, 0) + 1
        if self.failures[provider] >= self.failure_threshold:
            self.opened_at[provider] = self.clock()
            print(f"[CIRCUIT BREAKER] Opened for {provider} after {self.failures[provider]} consecutive failures")

    def snapshot(self) -> dict[str, dict]:
        providers = set(self.failures) | set(self.opened_at)
        return {p: {"state": self.state(p), "consecutive_failures": self.failures.get(p, 0)} for p in sorted(providers)}

    def reset(self) -> None:
        self.failures.clear()
        self.opened_at.clear()
        self.trial_in_flight.clear()


# Shared by all executions so provider health is learned across workflows
circuit_breaker = CircuitBreaker()


class CircuitOpenError(Exception):
    def __init__(self, provider: str):
        super().__init__(f"Circuit open for provider '{provider}': too many recent failures")
        self.provider = provider


class LLMCallFailed(Exception):
    """All attempts on one model failed. `attempts` describes each failure."""

    def __init__(self, provider: str, model: Optional[str], attempts: list[dict], last_error: Exception):
        self.provider = provider
        self.model = model
        self.attempts = attempts
        self.last_error = last_error
        self.error_type = attempts[-1]["error_type"] if attempts else classify_error(last_error)
        super().__init__(
            f"{provider}/{model} failed after {len(attempts)} attempt(s): "
            f"{type(last_error).__name__}: {last_error}"
        )


class ErrorHandler:
    """Calls an LLM provider with timeouts, classified retries and backoff, honouring the circuit breaker."""

    def __init__(self, breaker: Optional[CircuitBreaker] = None, max_retries: Optional[int] = None,
                 timeout_seconds: Optional[float] = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self.breaker = breaker or circuit_breaker
        self.max_retries = max_retries or settings.MAX_RETRIES
        self.timeout_seconds = timeout_seconds or settings.STAGE_TIMEOUT_SECONDS
        self.sleep = sleep

    @staticmethod
    def backoff_delay(error_type: str, attempt: int) -> float:
        """Seconds to wait after failed attempt number `attempt` (1-based)."""
        if error_type == RATE_LIMIT:
            return settings.RATE_LIMIT_BACKOFF_SECONDS
        return settings.RETRY_BACKOFF_INITIAL_SECONDS * settings.RETRY_BACKOFF_BASE ** (attempt - 1)

    async def call(self, provider: BaseLLMProvider, prompt: str, model: Optional[str],
                   system_prompt: Optional[str] = None) -> tuple[LLMResponse, list[dict]]:
        """
        Returns (response, failed_attempts). Raises CircuitOpenError if the provider's
        circuit refuses the call, or LLMCallFailed once retries are exhausted or the
        error is permanent.
        """
        name = provider.provider_name
        attempts: list[dict] = []
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            if not self.breaker.allow_request(name):
                if not attempts:
                    raise CircuitOpenError(name)
                break  # circuit opened during our retries: stop hammering the provider
            try:
                response = await asyncio.wait_for(
                    provider.generate(prompt=prompt, model=model, system_prompt=system_prompt),
                    timeout=self.timeout_seconds,
                )
                self.breaker.record_success(name)
                if attempts:
                    print(f"[RETRY] {name}/{model} succeeded on attempt {attempt}")
                return response, attempts
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"LLM call timed out after {self.timeout_seconds}s")
            except Exception as e:
                last_error = e

            error_type = classify_error(last_error)
            attempts.append({
                "provider": name, "model": model, "attempt": attempt,
                "error_type": error_type, "error": f"{type(last_error).__name__}: {last_error}"[:500],
            })
            print(f"[ERROR] {name}/{model} attempt {attempt}/{self.max_retries} ({error_type}): {last_error}")

            if error_type == PERMANENT:
                # A bad request says nothing about provider health; auth/model errors are fixed by fallback, not waiting
                self.breaker.trial_in_flight.discard(name)
                break
            self.breaker.record_failure(name)
            if attempt < self.max_retries:
                await self.sleep(self.backoff_delay(error_type, attempt))

        raise LLMCallFailed(name, model, attempts, last_error)
