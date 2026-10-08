"""
Semantic Cache Service.
Handles cache lookup via cosine similarity search and cache storage using pgvector.
"""
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.cache import CacheEntry
from backend.app.models.stage import Stage
from backend.app.schemas.cache import CacheEntryResponse, CacheHitResponse
from backend.app.services.cache.cache_validator import CacheValidator
from backend.app.services.embedding_service import get_embedding_service


class SemanticCacheService:
    """Service for semantic caching with vector similarity search."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = get_embedding_service()
        self.validator = CacheValidator(db)
        self.similarity_threshold = float(settings.CACHE_SIMILARITY_THRESHOLD)

    async def lookup(
        self,
        input_text: str,
        stage_type: Optional[str] = None,
        dependency_hash: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
        embedding: Optional[list[float]] = None,
    ) -> CacheHitResponse:
        """
        Look up a cache entry via cosine similarity search.

        Args:
            input_text: The input text to search for.
            stage_type: Optional filter by stage type.
            dependency_hash: Optional dependency hash for validation.
            similarity_threshold: Override the default threshold.

        Returns:
            CacheHitResponse with cache_hit=True if a match is found.
        """
        threshold = similarity_threshold if similarity_threshold is not None else self.similarity_threshold

        # Generate embedding for the query (unless the caller already has it)
        if embedding is None:
            embedding = await self.embedding_service.generate_embedding(input_text)

        # cosine_distance returns 0 for identical vectors, 2 for opposite.
        # similarity = 1 - cosine_distance
        similarity_expr = (
            1 - CacheEntry.input_embedding.cosine_distance(embedding)
        ).label("similarity")

        query = (
            select(CacheEntry, similarity_expr)
            .where(
                CacheEntry.is_valid == True,
                (1 - CacheEntry.input_embedding.cosine_distance(embedding)) >= threshold,
                (CacheEntry.expires_at.is_(None)) | (CacheEntry.expires_at > datetime.now(timezone.utc)),
            )
            .order_by(text("similarity DESC"))
            .limit(1)
        )

        if stage_type:
            query = query.where(CacheEntry.stage_type == stage_type)
        if dependency_hash:
            query = query.where(CacheEntry.dependency_hash == dependency_hash)

        result = await self.db.execute(query)
        row = result.first()

        if not row:
            return CacheHitResponse(cache_hit=False)

        cache_entry, similarity_score = row

        # Increment hit count
        await self._increment_hit_count(cache_entry.id)

        tokens_saved = cache_entry.result_tokens or 0
        cost_saved = self._estimate_cost_saved(tokens_saved)

        entry_response = CacheEntryResponse.model_validate(cache_entry)
        entry_response.similarity_score = float(similarity_score)

        return CacheHitResponse(
            cache_hit=True,
            entry=entry_response,
            similarity_score=float(similarity_score),
            tokens_saved=tokens_saved,
            cost_saved=cost_saved,
        )

    async def store(
        self,
        input_text: str,
        result: str,
        stage_type: Optional[str] = None,
        workflow_id: Optional[uuid.UUID] = None,
        stage_id: Optional[uuid.UUID] = None,
        result_tokens: Optional[int] = None,
        model_used: Optional[str] = None,
        dependency_hash: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        embedding: Optional[list[float]] = None,
    ) -> CacheEntry:
        """
        Store a new cache entry with its embedding.

        Args:
            input_text: The input text to embed and cache.
            result: The LLM result to store.
            stage_type: Type of stage (analysis, design, generation, etc.)
            workflow_id: Associated workflow ID.
            stage_id: Associated stage ID.
            result_tokens: Number of tokens in the result.
            model_used: Name of the model that produced the result.
            dependency_hash: Hash of upstream stage outputs for invalidation.
            ttl_seconds: Time-to-live in seconds (None = no expiry).
            embedding: Precomputed embedding of input_text (generated if omitted).

        Returns:
            The created CacheEntry ORM instance.
        """
        if embedding is None:
            embedding = await self.embedding_service.generate_embedding(input_text)

        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        cache_entry = CacheEntry(
            workflow_id=workflow_id,
            stage_id=stage_id,
            stage_type=stage_type,
            input_text=input_text,
            input_embedding=embedding,
            result=result,
            result_tokens=result_tokens,
            model_used=model_used,
            dependency_hash=dependency_hash,
            similarity_threshold=Decimal(str(self.similarity_threshold)),
            expires_at=expires_at,
        )

        self.db.add(cache_entry)
        await self.db.flush()

        return cache_entry

    async def lookup_with_validation(
        self,
        input_text: str,
        workflow_id: uuid.UUID,
        execution_id: uuid.UUID,
        current_stage: Stage,
        similarity_threshold: Optional[float] = None,
        embedding: Optional[list[float]] = None,
    ) -> CacheHitResponse:
        """
        Workflow-aware cache lookup.

        Only entries whose dependency hash matches the current upstream outputs
        are considered, and the hit is re-validated before being returned.
        With CACHE_ENABLE_WORKFLOW_VALIDATION off, this is a plain lookup.
        """
        if not settings.CACHE_ENABLE_WORKFLOW_VALIDATION:
            return await self.lookup(
                input_text=input_text,
                stage_type=current_stage.stage_type,
                similarity_threshold=similarity_threshold,
                embedding=embedding,
            )

        dependency_hash = await self.validator.compute_dependency_hash(
            workflow_id, execution_id, current_stage
        )

        result = await self.lookup(
            input_text=input_text,
            stage_type=current_stage.stage_type,
            dependency_hash=dependency_hash,
            similarity_threshold=similarity_threshold,
            embedding=embedding,
        )

        if result.cache_hit and result.entry:
            cache_entry = await self.db.get(CacheEntry, result.entry.id)
            if cache_entry is None or not await self.validator.is_cache_valid(
                cache_entry, dependency_hash
            ):
                return CacheHitResponse(cache_hit=False)

        return result

    async def store_with_dependencies(
        self,
        input_text: str,
        result: str,
        workflow_id: uuid.UUID,
        execution_id: uuid.UUID,
        current_stage: Stage,
        result_tokens: Optional[int] = None,
        model_used: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        embedding: Optional[list[float]] = None,
    ) -> CacheEntry:
        """
        Store a cache entry tagged with the current upstream dependency hash.

        ttl_seconds defaults to CACHE_TTL_SECONDS; pass 0 for no expiry.
        """
        dependency_hash = await self.validator.compute_dependency_hash(
            workflow_id, execution_id, current_stage
        )

        return await self.store(
            input_text=input_text,
            result=result,
            stage_type=current_stage.stage_type,
            workflow_id=workflow_id,
            stage_id=current_stage.id,
            result_tokens=result_tokens,
            model_used=model_used,
            dependency_hash=dependency_hash,
            ttl_seconds=settings.CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds,
            embedding=embedding,
        )

    async def invalidate(
        self,
        workflow_id: Optional[uuid.UUID] = None,
        stage_id: Optional[uuid.UUID] = None,
        stage_type: Optional[str] = None,
    ) -> int:
        """
        Invalidate cache entries by marking them as invalid.

        Args:
            workflow_id: Invalidate all entries for a workflow.
            stage_id: Invalidate all entries for a stage.
            stage_type: Invalidate all entries of a stage type.

        Returns:
            Number of entries invalidated.
        """
        query = (
            update(CacheEntry)
            .where(CacheEntry.is_valid == True)
            .values(is_valid=False)
        )

        if workflow_id:
            query = query.where(CacheEntry.workflow_id == workflow_id)
        if stage_id:
            query = query.where(CacheEntry.stage_id == stage_id)
        if stage_type:
            query = query.where(CacheEntry.stage_type == stage_type)

        result = await self.db.execute(query)
        await self.db.flush()

        return result.rowcount

    async def clear_expired(self) -> int:
        """
        Mark expired cache entries as invalid.

        Returns:
            Number of entries expired.
        """
        query = (
            update(CacheEntry)
            .where(
                CacheEntry.expires_at.isnot(None),
                CacheEntry.expires_at < datetime.now(timezone.utc),
                CacheEntry.is_valid == True,
            )
            .values(is_valid=False)
        )

        result = await self.db.execute(query)
        await self.db.flush()

        return result.rowcount

    async def _increment_hit_count(self, entry_id: uuid.UUID) -> None:
        """Atomically increment the hit count for a cache entry."""
        await self.db.execute(
            update(CacheEntry)
            .where(CacheEntry.id == entry_id)
            .values(hit_count=CacheEntry.hit_count + 1)
        )
        await self.db.flush()

    @staticmethod
    def _estimate_cost_saved(tokens: int, model: str = "gpt-4o-mini") -> Decimal:
        """Estimate cost saved from a cache hit (simplified)."""
        # ~$0.001 per 1K output tokens
        cost_per_token = Decimal("0.000001")
        return Decimal(tokens) * cost_per_token

    @staticmethod
    def compute_dependency_hash(dependency_outputs: List[str]) -> str:
        """
        Compute a deterministic hash of upstream stage outputs.
        Used to validate that cache entries remain coherent when dependencies change.
        """
        combined = "||".join(dependency_outputs)
        return hashlib.sha256(combined.encode()).hexdigest()
