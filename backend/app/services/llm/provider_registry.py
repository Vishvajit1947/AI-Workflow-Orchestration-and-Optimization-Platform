"""Registry for LLM providers — singleton that holds all initialized providers."""
from typing import Optional
from backend.app.services.llm.base import BaseLLMProvider


class ProviderRegistry:
    _instance: Optional["ProviderRegistry"] = None
    _providers: dict[str, BaseLLMProvider] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._providers = {}
        return cls._instance

    def register(self, provider: BaseLLMProvider) -> None:
        self._providers[provider.provider_name] = provider

    def get(self, name: str) -> BaseLLMProvider:
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' not registered. Available: {list(self._providers.keys())}")
        return self._providers[name]

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def get_all(self) -> dict[str, BaseLLMProvider]:
        return dict(self._providers)


registry = ProviderRegistry()
