"""Google Gemini LLM provider."""
import time
from typing import Optional
import google.generativeai as genai
from backend.app.config import settings
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse

# Pricing per 1M tokens (verified June 2025)
GEMINI_PRICING = {
    "gemini-2.5-flash": {"input": 0.00, "output": 0.00},       # stable, free
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},          # stable, paid
    "gemini-flash-latest": {"input": 0.00, "output": 0.00},     # alias for latest flash
    "gemini-pro-latest": {"input": 1.25, "output": 5.00},       # alias for latest pro
    "gemini-3.8-flash": {"input": 0.00, "output": 0.00},        # newer flash
    "gemini-3.5-flash": {"input": 0.00, "output": 0.00},        # newer flash
}


class GeminiProvider(BaseLLMProvider):
    provider_name = "gemini"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini provider.
        
        Args:
            api_key: Optional API key. If not provided, uses settings.GOOGLE_API_KEY
        """
        key = api_key or settings.GOOGLE_API_KEY
        genai.configure(api_key=key)

    async def generate(self, prompt: str, model: Optional[str] = None,
                       temperature: float = 0.7, max_tokens: int = 4096,
                       system_prompt: Optional[str] = None) -> LLMResponse:
        model_name = model or self.get_default_model()
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        gen_model = genai.GenerativeModel(model_name)
        config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )

        start = time.perf_counter()
        response = await gen_model.generate_content_async(
            full_prompt,
            generation_config=config
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        # Handle safety blocks or empty responses gracefully
        try:
            content = response.text if response.text else ""
        except ValueError:
            # Response was blocked by safety filters
            content = "[Response blocked by Gemini safety filters]"
        
        # Extract token usage from metadata
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0

        return LLMResponse(
            content=content,
            model=model_name,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            estimated_cost=self.estimate_cost(input_tokens, output_tokens, model_name),
        )

    def get_available_models(self) -> list[dict]:
        return [
            {"model": "gemini-2.5-flash", "description": "Gemini 2.5 Flash — stable, fast, 1M context (free)", "context_window": 1048576},
            {"model": "gemini-2.5-pro", "description": "Gemini 2.5 Pro — most capable, 1M context", "context_window": 1048576},
            {"model": "gemini-3.8-flash", "description": "Gemini 3.8 Flash — latest generation (free)", "context_window": 1048576},
            {"model": "gemini-flash-latest", "description": "Latest Gemini Flash (free tier)", "context_window": 1048576},
            {"model": "gemini-pro-latest", "description": "Latest Gemini Pro stable", "context_window": 1048576},
        ]

    def get_default_model(self) -> str:
        # gemini-pro-latest: stable alias to latest pro model
        return "gemini-pro-latest"

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = GEMINI_PRICING.get(model, GEMINI_PRICING["gemini-2.5-flash"])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
