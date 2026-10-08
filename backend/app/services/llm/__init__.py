"""LLM provider package — register all providers on import."""
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse
from backend.app.services.llm.provider_registry import registry
from backend.app.config import settings


def init_providers():
    """Initialize and register available providers based on API keys."""
    if settings.OPENAI_API_KEY:
        from backend.app.services.llm.openai_provider import OpenAIProvider
        registry.register(OpenAIProvider())
    
    if settings.ANTHROPIC_API_KEY:
        from backend.app.services.llm.anthropic_provider import AnthropicProvider
        registry.register(AnthropicProvider())
    
    if settings.GOOGLE_API_KEY:
        from backend.app.services.llm.gemini_provider import GeminiProvider
        registry.register(GeminiProvider())
    
    if settings.GROQ_API_KEY:
        from backend.app.services.llm.groq_provider import GroqProvider
        registry.register(GroqProvider())


# Auto-init when module is imported
init_providers()

__all__ = ["BaseLLMProvider", "LLMResponse", "registry"]
