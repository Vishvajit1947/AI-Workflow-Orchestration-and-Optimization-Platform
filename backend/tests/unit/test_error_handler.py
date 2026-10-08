"""
Error handler unit tests: classification, retries/backoff, timeouts, circuit breaker.
"""
import asyncio

import pytest

from backend.app.config import settings
from backend.app.services.execution.error_handler import (
    PERMANENT, RATE_LIMIT, TRANSIENT, CircuitBreaker, CircuitOpenError, ErrorHandler, LLMCallFailed,
    classify_error,
)
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse


class HTTPError(Exception):
    def __init__(self, status_code: int, message: str = "error"):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(Exception):
    pass


class FlakyProvider(BaseLLMProvider):
    """Raises the queued errors in order, then succeeds."""
    provider_name = "flaky"

    def __init__(self, errors=(), delay: float = 0.0):
        self.errors = list(errors)
        self.delay = delay
        self.calls = 0

    async def generate(self, prompt, model=None, temperature=0.7, max_tokens=4096, system_prompt=None):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.errors:
            raise self.errors.pop(0)
        return LLMResponse(content="ok", model=model or "m", provider=self.provider_name,
                           input_tokens=1, output_tokens=1, total_tokens=2, latency_ms=1, estimated_cost=0)

    def get_available_models(self):
        return []

    def get_default_model(self):
        return "m"


class RecordingSleep:
    def __init__(self):
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


# ---------- classification ----------

@pytest.mark.parametrize("error, expected", [
    (HTTPError(429), RATE_LIMIT),
    (HTTPError(500), TRANSIENT),
    (HTTPError(503), TRANSIENT),
    (HTTPError(408), TRANSIENT),
    (HTTPError(400), PERMANENT),
    (HTTPError(401), PERMANENT),
    (HTTPError(404), PERMANENT),
    (TimeoutError("slow"), TRANSIENT),
    (ConnectionError("reset"), TRANSIENT),
    (RateLimitError("slow down"), RATE_LIMIT),
    (Exception("You exceeded your current quota"), RATE_LIMIT),
    (Exception("Incorrect API key provided"), PERMANENT),
    (ValueError("Provider 'x' not registered. Available: []"), PERMANENT),
    (Exception("error code 5001 in payload"), TRANSIENT),  # no substring match on "500"
    (Exception("something odd"), TRANSIENT),
])
def test_classify_error(error, expected):
    assert classify_error(error) == expected


# ---------- retries ----------

async def test_retries_transient_errors_with_exponential_backoff(monkeypatch):
    monkeypatch.setattr(settings, "RETRY_BACKOFF_INITIAL_SECONDS", 1.0)
    monkeypatch.setattr(settings, "RETRY_BACKOFF_BASE", 2)
    sleep = RecordingSleep()
    provider = FlakyProvider([HTTPError(503), HTTPError(502)])
    handler = ErrorHandler(breaker=CircuitBreaker(failure_threshold=10), max_retries=3, sleep=sleep)

    response, attempts = await handler.call(provider, "prompt", "m")

    assert response.content == "ok"
    assert provider.calls == 3
    assert sleep.delays == [1.0, 2.0]
    assert [a["error_type"] for a in attempts] == [TRANSIENT, TRANSIENT]


async def test_rate_limit_uses_longer_backoff(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKOFF_SECONDS", 30.0)
    sleep = RecordingSleep()
    handler = ErrorHandler(breaker=CircuitBreaker(failure_threshold=10), max_retries=2, sleep=sleep)
    await handler.call(FlakyProvider([HTTPError(429)]), "prompt", "m")
    assert sleep.delays == [30.0]


async def test_permanent_error_is_not_retried():
    sleep = RecordingSleep()
    breaker = CircuitBreaker(failure_threshold=1)
    provider = FlakyProvider([HTTPError(401, "bad key")])
    with pytest.raises(LLMCallFailed) as info:
        await ErrorHandler(breaker=breaker, max_retries=3, sleep=sleep).call(provider, "prompt", "m")

    assert provider.calls == 1
    assert sleep.delays == []
    assert info.value.error_type == PERMANENT
    assert breaker.state("flaky") == "closed"  # a bad request isn't a provider outage


async def test_gives_up_after_max_retries():
    provider = FlakyProvider([HTTPError(500)] * 5)
    with pytest.raises(LLMCallFailed) as info:
        await ErrorHandler(breaker=CircuitBreaker(failure_threshold=10), max_retries=3,
                           sleep=RecordingSleep()).call(provider, "prompt", "m")
    assert provider.calls == 3
    assert len(info.value.attempts) == 3
    assert "failed after 3 attempt(s)" in str(info.value)


async def test_timeout_per_attempt():
    provider = FlakyProvider(delay=1.0)
    handler = ErrorHandler(breaker=CircuitBreaker(failure_threshold=10), max_retries=2,
                           timeout_seconds=0.05, sleep=RecordingSleep())
    with pytest.raises(LLMCallFailed) as info:
        await handler.call(provider, "prompt", "m")
    assert provider.calls == 2
    assert all(a["error_type"] == TRANSIENT and "timed out" in a["error"] for a in info.value.attempts)


# ---------- circuit breaker ----------

class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_circuit_opens_after_threshold_and_is_per_provider():
    breaker = CircuitBreaker(failure_threshold=3, timeout=60, clock=FakeClock())
    for _ in range(2):
        breaker.record_failure("openai")
    assert breaker.state("openai") == "closed"
    breaker.record_failure("openai")
    assert breaker.is_open("openai")
    assert not breaker.allow_request("openai")
    assert not breaker.is_open("anthropic")


def test_circuit_half_open_allows_one_trial():
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, timeout=60, clock=clock)
    breaker.record_failure("openai")
    clock.now = 61
    assert breaker.state("openai") == "half_open"
    assert breaker.allow_request("openai")       # the trial call
    assert not breaker.allow_request("openai")   # others wait for it
    breaker.record_success("openai")
    assert breaker.state("openai") == "closed"


def test_failed_half_open_trial_reopens():
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, timeout=60, clock=clock)
    breaker.record_failure("openai")
    clock.now = 61
    assert breaker.allow_request("openai")
    breaker.record_failure("openai")
    assert breaker.state("openai") == "open"
    clock.now = 100
    assert breaker.state("openai") == "open"  # open period restarted at t=61
    clock.now = 122
    assert breaker.state("openai") == "half_open"


async def test_open_circuit_refuses_calls_and_stops_retries():
    breaker = CircuitBreaker(failure_threshold=2, timeout=60)
    provider = FlakyProvider([HTTPError(500)] * 5)
    handler = ErrorHandler(breaker=breaker, max_retries=5, sleep=RecordingSleep())

    with pytest.raises(LLMCallFailed):
        await handler.call(provider, "prompt", "m")
    assert provider.calls == 2  # circuit opened after 2 failures, no more hammering

    with pytest.raises(CircuitOpenError):
        await handler.call(provider, "prompt", "m")
    assert provider.calls == 2
