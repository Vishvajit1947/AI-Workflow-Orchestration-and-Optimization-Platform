"""
Cache Validator.
Workflow-aware cache validation using dependency hashes and TTL.
"""
import hashlib
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.cache import CacheEntry
from backend.app.models.stage import Stage, StageDependency
from backend.app.services.context_manager import ContextManager


class CacheValidator:
    """Validates cache entries based on workflow dependencies."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.context_mgr = ContextManager(db)

    async def compute_dependency_hash(
        self,
        workflow_id: uuid.UUID,
        execution_id: uuid.UUID,
        current_stage: Stage,
    ) -> str:
        """
        Compute a SHA-256 hash of the upstream stage outputs feeding `current_stage`.

        Uses the same dependency selection as ContextManager (explicit dependencies,
        falling back to the immediately preceding stage), so the hash reflects exactly
        the context the stage would receive.
        """
        contexts = await self.context_mgr.get_relevant_context(
            workflow_id, execution_id, current_stage.id
        )

        # Deterministic order: creation time, then content as a tie-breaker
        # (rows written in the same transaction share the same now()).
        dependency_outputs = [
            ctx.content
            for ctx in sorted(contexts, key=lambda c: (c.created_at, c.content))
            if ctx.context_type == "stage_output"
        ]

        if not dependency_outputs:
            return hashlib.sha256(b"").hexdigest()

        combined = "||".join(dependency_outputs)
        return hashlib.sha256(combined.encode()).hexdigest()

    async def is_cache_valid(
        self,
        cache_entry: CacheEntry,
        current_dependency_hash: Optional[str] = None,
    ) -> bool:
        """
        Check whether a cache entry is still usable.

        Invalid if explicitly marked invalid, past its TTL, or its stored
        dependency hash differs from the current one.
        """
        if not cache_entry.is_valid:
            return False

        if cache_entry.expires_at and datetime.now(timezone.utc) > cache_entry.expires_at:
            return False

        if current_dependency_hash and cache_entry.dependency_hash:
            if current_dependency_hash != cache_entry.dependency_hash:
                return False

        return True

    async def invalidate_downstream_cache(
        self,
        workflow_id: uuid.UUID,
        changed_stage_id: uuid.UUID,
    ) -> int:
        """
        Invalidate cache entries for every stage downstream of `changed_stage_id`.

        When a stage is re-executed its output may change, so all dependent
        stages' cached results become stale.

        Returns:
            Number of cache entries invalidated.
        """
        result = await self.db.execute(select(Stage).where(Stage.id == changed_stage_id))
        changed_stage = result.scalar_one_or_none()
        if not changed_stage:
            return 0

        result = await self.db.execute(select(Stage).where(Stage.workflow_id == workflow_id))
        all_stages = list(result.scalars().all())

        downstream_stage_ids = await self._find_downstream_stages(changed_stage, all_stages)
        if not downstream_stage_ids:
            return 0

        result = await self.db.execute(
            update(CacheEntry)
            .where(
                CacheEntry.workflow_id == workflow_id,
                CacheEntry.stage_id.in_(downstream_stage_ids),
                CacheEntry.is_valid == True,
            )
            .values(is_valid=False)
        )
        await self.db.flush()

        return result.rowcount

    async def _find_downstream_stages(
        self,
        changed_stage: Stage,
        all_stages: List[Stage],
    ) -> List[uuid.UUID]:
        """
        Find all stages downstream of the changed stage.

        A stage is downstream if:
        1. It has a higher stage_order (sequential execution), or
        2. It transitively depends on the changed stage via stage_dependencies.
        Over-invalidating is safe; missing a stale entry is not.
        """
        stage_ids = {s.id for s in all_stages}
        downstream = {
            s.id for s in all_stages if s.stage_order > changed_stage.stage_order
        }

        # Explicit dependency graph: depends_on_stage_id -> [stage_id, ...]
        result = await self.db.execute(
            select(StageDependency.stage_id, StageDependency.depends_on_stage_id)
            .where(StageDependency.stage_id.in_(stage_ids))
        )
        dependents: dict[uuid.UUID, list[uuid.UUID]] = {}
        for stage_id, depends_on_id in result.fetchall():
            dependents.setdefault(depends_on_id, []).append(stage_id)

        queue = deque([changed_stage.id])
        visited = {changed_stage.id}
        while queue:
            for child in dependents.get(queue.popleft(), []):
                if child not in visited:
                    visited.add(child)
                    downstream.add(child)
                    queue.append(child)

        downstream.discard(changed_stage.id)
        return list(downstream)

    async def cleanup_expired_entries(self) -> int:
        """
        Mark expired cache entries as invalid.
        Intended to run periodically (e.g. a daily job).

        Returns:
            Number of entries cleaned up.
        """
        result = await self.db.execute(
            update(CacheEntry)
            .where(
                CacheEntry.expires_at.isnot(None),
                CacheEntry.expires_at < datetime.now(timezone.utc),
                CacheEntry.is_valid == True,
            )
            .values(is_valid=False)
        )
        await self.db.flush()

        return result.rowcount
