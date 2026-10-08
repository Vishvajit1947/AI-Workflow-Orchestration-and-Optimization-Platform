"""Groq LLM provider - Fast inference on LPU."""
import time
from typing import Optional
from groq import AsyncGroq
from backend.app.config import settings
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse

# Groq pricing per 1M tokens (verified live models as of Oct 2026)
GROQ_PRICING = {
    "openai/gpt-oss-20b": {"input": 0.10, "output": 0.15},
    "openai/gpt-oss-120b": {"input": 0.50, "output": 0.75},
    "qwen/qwen3.8-27b": {"input": 0.20, "output": 0.30},
    "allam-2-7b": {"input": 0.05, "output": 0.08},
}


class GroqProvider(BaseLLMProvider):
    provider_name = "groq"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Groq provider.
        
        Args:
            api_key: Optional API key. If not provided, uses settings.GROQ_API_KEY
        """
        key = api_key or settings.GROQ_API_KEY or "test-key"
        # Initialize Groq client - pass httpx client to avoid version incompatibility
        try:
            import httpx
            self.client = AsyncGroq(
                api_key=key,
                http_client=httpx.AsyncClient()
            )
        except Exception:
            try:
                self.client = AsyncGroq(api_key=key)
            except Exception:
                self.client = None

    async def generate(self, prompt: str, model: Optional[str] = None,
                       temperature: float = 0.7, max_tokens: int = 4096,
                       system_prompt: Optional[str] = None) -> LLMResponse:
        model = model or self.get_default_model()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.perf_counter()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        usage = response.usage
        choice = response.choices[0]
        # Some Groq models (gpt-oss-*) use reasoning tokens; content may arrive
        # via the reasoning summary or be empty for short prompts — handle gracefully.
        content = choice.message.content or ""
        if not content and hasattr(choice.message, "reasoning") and choice.message.reasoning:
            content = choice.message.reasoning
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            latency_ms=latency_ms,
            estimated_cost=self.estimate_cost(
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0,
                model
            ),
        )

    def get_available_models(self) -> list[dict]:
        return [
            {"model": "qwen/qwen3.8-27b", "description": "Qwen 27B on Groq LPU (recommended)", "context_window": 32768},
            {"model": "openai/gpt-oss-20b", "description": "OpenAI OSS 20B reasoning model via Groq", "context_window": 131072},
            {"model": "openai/gpt-oss-120b", "description": "OpenAI OSS 120B reasoning model via Groq", "context_window": 131072},
            {"model": "allam-2-7b", "description": "Allam 2 7B — fast & lightweight", "context_window": 4096},
        ]

    def get_default_model(self) -> str:
        # qwen3.8-27b is preferred: reliable content output, no reasoning-token quirks
        return "qwen/qwen3.8-27b"

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = GROQ_PRICING.get(model, GROQ_PRICING["qwen/qwen3.8-27b"])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
