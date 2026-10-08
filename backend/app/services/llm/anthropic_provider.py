"""Anthropic (Claude) LLM provider."""
import time
from typing import Optional
from anthropic import AsyncAnthropic
from backend.app.config import settings
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse

# Pricing per 1M tokens (as of Dec 2024)
ANTHROPIC_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
}


class AnthropicProvider(BaseLLMProvider):
    provider_name = "anthropic"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Anthropic provider.
        
        Args:
            api_key: Optional API key. If not provided, uses settings.ANTHROPIC_API_KEY
        """
        key = api_key or settings.ANTHROPIC_API_KEY
        self.client = AsyncAnthropic(api_key=key)

    async def generate(self, prompt: str, model: Optional[str] = None,
                       temperature: float = 0.7, max_tokens: int = 4096,
                       system_prompt: Optional[str] = None) -> LLMResponse:
        model = model or self.get_default_model()
        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        if system_prompt:
            kwargs["system"] = system_prompt

        start = time.perf_counter()
        response = await self.client.messages.create(**kwargs)
        latency_ms = int((time.perf_counter() - start) * 1000)

        content = response.content[0].text if response.content else ""
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            latency_ms=latency_ms,
            estimated_cost=self.estimate_cost(
                response.usage.input_tokens,
                response.usage.output_tokens,
                model
            ),
        )

    def get_available_models(self) -> list[dict]:
        return [
            {"model": "claude-sonnet-4-20250514", "description": "Best balance of speed and intelligence", "context_window": 200000},
            {"model": "claude-3-5-haiku-20241022", "description": "Fastest Claude model", "context_window": 200000},
            {"model": "claude-3-opus-20240229", "description": "Most capable Claude", "context_window": 200000},
        ]

    def get_default_model(self) -> str:
        return "claude-sonnet-4-20250514"

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = ANTHROPIC_PRICING.get(model, ANTHROPIC_PRICING["claude-sonnet-4-20250514"])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
