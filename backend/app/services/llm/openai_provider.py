"""OpenAI LLM provider implementation."""
import time
from typing import Optional
from openai import AsyncOpenAI
from backend.app.config import settings
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse

# Pricing per 1M tokens (as of Dec 2024)
OPENAI_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


class OpenAIProvider(BaseLLMProvider):
    provider_name = "openai"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: Optional API key. If not provided, uses settings.OPENAI_API_KEY
        """
        key = api_key or settings.OPENAI_API_KEY
        self.client = AsyncOpenAI(api_key=key)

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
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=model, provider=self.provider_name,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            latency_ms=latency_ms,
            estimated_cost=self.estimate_cost(
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0, model),
        )

    def get_available_models(self) -> list[dict]:
        return [
            {"model": "gpt-4o", "description": "Most capable, multimodal", "context_window": 128000},
            {"model": "gpt-4o-mini", "description": "Fast and affordable", "context_window": 128000},
            {"model": "gpt-4-turbo", "description": "GPT-4 Turbo", "context_window": 128000},
            {"model": "gpt-3.5-turbo", "description": "Fast, legacy", "context_window": 16385},
        ]

    def get_default_model(self) -> str:
        return "gpt-4o-mini"

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = OPENAI_PRICING.get(model, OPENAI_PRICING["gpt-4o-mini"])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
