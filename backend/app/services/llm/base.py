"""Abstract base class for LLM providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    estimated_cost: float
    raw_response: Optional[dict] = None


class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers."""
    provider_name: str = "base"

    @abstractmethod
    async def generate(self, prompt: str, model: Optional[str] = None,
                       temperature: float = 0.7, max_tokens: int = 4096,
                       system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    @abstractmethod
    def get_available_models(self) -> list[dict]:
        """Return list of available models with capabilities."""
        ...

    @abstractmethod
    def get_default_model(self) -> str:
        """Return the default model name."""
        ...

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost based on token counts. Override per provider."""
        return 0.0
