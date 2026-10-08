"""
Model Registry Service.
Catalogs available models with capability scores, pricing and latency.
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.model_profile import ModelProfile

# Capability scored for stages with no type, or type "custom"
GENERAL_CAPABILITY = "reasoning"

# Every capability key a seeded profile scores
CAPABILITIES = ["analysis", "design", "generation", "testing", "documentation", "review", GENERAL_CAPABILITY]


def capability_for_stage_type(stage_type: Optional[str]) -> str:
    """Capability key used to score models for a stage type."""
    if stage_type in CAPABILITIES:
        return stage_type
    return GENERAL_CAPABILITY


class ModelRegistry:
    """Register and look up model profiles."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_model(self, provider: str, model_name: str, display_name: str,
                             capabilities: dict[str, float], max_context_tokens: int,
                             cost_per_input_token: Decimal, cost_per_output_token: Decimal,
                             overwrite: bool = True, **kwargs) -> ModelProfile:
        """
        Create a model profile, or update the existing one for (provider, model_name).
        With overwrite=False an existing profile is returned untouched.
        """
        existing = await self.get_model(provider, model_name)
        fields = dict(
            display_name=display_name,
            capabilities=capabilities,
            max_context_tokens=max_context_tokens,
            cost_per_input_token=cost_per_input_token,
            cost_per_output_token=cost_per_output_token,
            **kwargs,
        )
        if existing:
            if overwrite:
                for key, value in fields.items():
                    setattr(existing, key, value)
                await self.db.flush()
            return existing

        profile = ModelProfile(provider=provider, model_name=model_name, **fields)
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def get_model(self, provider: str, model_name: str) -> Optional[ModelProfile]:
        result = await self.db.execute(
            select(ModelProfile).where(
                ModelProfile.provider == provider,
                ModelProfile.model_name == model_name,
            )
        )
        return result.scalar_one_or_none()

    async def list_models(self, provider: Optional[str] = None,
                          available_only: bool = True) -> list[ModelProfile]:
        query = select(ModelProfile)
        if provider:
            query = query.where(ModelProfile.provider == provider)
        if available_only:
            query = query.where(ModelProfile.is_available.is_(True))
        query = query.order_by(ModelProfile.provider, ModelProfile.model_name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_models_for_capability(self, capability: str,
                                        min_score: float = 0.7) -> list[ModelProfile]:
        """Available models scoring at least min_score for the capability."""
        return [
            m for m in await self.list_models()
            if m.get_capability_score(capability) >= min_score
        ]

    async def get_cheapest_model(self, capability: Optional[str] = None,
                                 min_score: float = 0.7) -> Optional[ModelProfile]:
        models = (await self.get_models_for_capability(capability, min_score)
                  if capability else await self.list_models())
        return min(models, key=lambda m: m.avg_cost_per_token, default=None)

    async def get_fastest_model(self, capability: Optional[str] = None,
                                min_score: float = 0.7) -> Optional[ModelProfile]:
        models = (await self.get_models_for_capability(capability, min_score)
                  if capability else await self.list_models())
        timed = [m for m in models if m.avg_latency_ms is not None]
        return min(timed, key=lambda m: m.avg_latency_ms, default=None)

    async def get_most_capable_model(self, capability: str) -> Optional[ModelProfile]:
        models = await self.list_models()
        return max(models, key=lambda m: m.get_capability_score(capability), default=None)


def _per_token(usd_per_million: str) -> Decimal:
    return Decimal(usd_per_million) / Decimal(1_000_000)


def _scores(analysis, design, generation, testing, documentation, review, reasoning) -> dict[str, float]:
    return dict(zip(CAPABILITIES, [analysis, design, generation, testing, documentation, review, reasoning]))


# Provider names match each LLM provider's provider_name so the router can dispatch directly.
# Prices (USD per 1M tokens) mirror the pricing tables in services/llm/*_provider.py.
SEED_MODELS = [
    dict(provider="openai", model_name="gpt-4o", display_name="GPT-4o",
         capabilities=_scores(0.95, 0.92, 0.93, 0.90, 0.92, 0.93, 0.96),
         max_context_tokens=128_000, max_output_tokens=16_384,
         cost_per_input_token=_per_token("2.50"), cost_per_output_token=_per_token("10.00"),
         avg_latency_ms=2000, supports_streaming=True, supports_function_calling=True,
         description="Most capable GPT-4 class model, multimodal",
         strengths=["Complex reasoning", "Code generation", "Multimodal"],
         limitations=["Higher cost", "Slower than mini models"]),
    dict(provider="openai", model_name="gpt-4o-mini", display_name="GPT-4o Mini",
         capabilities=_scores(0.85, 0.83, 0.87, 0.82, 0.86, 0.83, 0.84),
         max_context_tokens=128_000, max_output_tokens=16_384,
         cost_per_input_token=_per_token("0.15"), cost_per_output_token=_per_token("0.60"),
         avg_latency_ms=800, supports_streaming=True, supports_function_calling=True,
         description="Fast and affordable GPT-4 class model",
         strengths=["Cost-effective", "Fast", "Good for most tasks"],
         limitations=["Weaker than GPT-4o on complex reasoning"]),
    dict(provider="anthropic", model_name="claude-sonnet-4-20250514", display_name="Claude Sonnet 4",
         capabilities=_scores(0.96, 0.94, 0.97, 0.94, 0.95, 0.96, 0.95),
         max_context_tokens=200_000, max_output_tokens=8192,
         cost_per_input_token=_per_token("3.00"), cost_per_output_token=_per_token("15.00"),
         avg_latency_ms=1800, supports_streaming=True, supports_function_calling=True,
         description="Strongest coding and analysis model in the catalog",
         strengths=["Superior code generation", "Large context window", "Careful reviews"],
         limitations=["Highest output cost"]),
    dict(provider="anthropic", model_name="claude-3-5-haiku-20241022", display_name="Claude 3.5 Haiku",
         capabilities=_scores(0.88, 0.85, 0.89, 0.85, 0.87, 0.86, 0.87),
         max_context_tokens=200_000, max_output_tokens=8192,
         cost_per_input_token=_per_token("0.80"), cost_per_output_token=_per_token("4.00"),
         avg_latency_ms=600, supports_streaming=True, supports_function_calling=True,
         description="Fastest Claude model with solid quality",
         strengths=["Very fast", "Large context window"],
         limitations=["Less capable than Sonnet"]),
    dict(provider="gemini", model_name="gemini-3.8-flash", display_name="Gemini 3.8 Flash",
         capabilities=_scores(0.89, 0.87, 0.90, 0.86, 0.88, 0.87, 0.88),
         max_context_tokens=1_048_576, max_output_tokens=65536,
         cost_per_input_token=_per_token("0"), cost_per_output_token=_per_token("0"),
         avg_latency_ms=800, supports_streaming=True, supports_function_calling=True,
         description="Latest stable Gemini 3.8 Flash with 1M-token context, free",
         strengths=["Large context window", "Free tier", "Multimodal", "Fast", "Latest generation"],
         limitations=["Free tier may have rate limits"]),
    dict(provider="groq", model_name="qwen/qwen3.8-27b", display_name="Qwen 3.8 27B (Groq)",
         capabilities=_scores(0.87, 0.85, 0.87, 0.83, 0.86, 0.85, 0.87),
         max_context_tokens=32_768, max_output_tokens=8192,
         cost_per_input_token=_per_token("0.20"), cost_per_output_token=_per_token("0.30"),
         avg_latency_ms=400, supports_streaming=True, supports_function_calling=True,
         description="Qwen 27B on Groq's low-latency inference",
         strengths=["Very low latency", "Low cost", "Reliable structured output"],
         limitations=["Smaller context window"]),
    dict(provider="groq", model_name="openai/gpt-oss-20b", display_name="GPT-OSS 20B (Groq)",
         capabilities=_scores(0.84, 0.81, 0.84, 0.80, 0.84, 0.81, 0.85),
         max_context_tokens=131_072, max_output_tokens=8192,
         cost_per_input_token=_per_token("0.10"), cost_per_output_token=_per_token("0.15"),
         avg_latency_ms=350, supports_streaming=True, supports_function_calling=True,
         description="OpenAI open-weights 20B reasoning model on Groq",
         strengths=["Very low latency", "Very cheap", "Large context window"],
         limitations=["Less capable than larger models"]),
]


async def seed_model_profiles(db: AsyncSession) -> None:
    """
    Insert seed models for providers that have API keys configured.
    Existing profiles (and user edits to them) are kept.
    Only seeds models for providers with configured API keys.
    """
    from backend.app.config import settings
    
    # Determine which providers are configured
    configured_providers = set()
    if settings.OPENAI_API_KEY:
        configured_providers.add("openai")
    if settings.ANTHROPIC_API_KEY:
        configured_providers.add("anthropic")
    if settings.GOOGLE_API_KEY:
        configured_providers.add("gemini")
    if settings.GROQ_API_KEY:
        configured_providers.add("groq")
    
    # Only seed models for configured providers
    registry = ModelRegistry(db)
    for spec in SEED_MODELS:
        if spec["provider"] in configured_providers:
            await registry.register_model(overwrite=False, **spec)
    
    await db.commit()
