"""
Execution Engine.
Runs a workflow's stages as a dependency graph (DAGAnalyzer): a stage starts as soon
as all its dependencies completed, up to MAX_PARALLEL_STAGES at once (1 when
parallel=False). For each stage: assemble context -> semantic cache -> route to a
model -> call it with retries/backoff/timeout -> on failure fall back to another
model -> store context, cache entry and execution record.

A failed stage skips its descendants; independent branches keep going.
Execution can be paused (no new stages start), resumed and cancelled (in-flight
LLM calls are cancelled) through the tracker's ExecutionControl.

The AsyncSession is not safe for concurrent use, so every database access runs
under one lock; only LLM calls (the slow part) overlap.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.config import settings
from backend.app.models.workflow import Workflow
from backend.app.models.stage import Stage
from backend.app.models.execution import ExecutionRecord
from backend.app.schemas.cache import CacheHitResponse
from backend.app.services.cache.semantic_cache import SemanticCacheService
from backend.app.services.context_manager import ContextManager
from backend.app.services.execution.dag_analyzer import DAGAnalyzer
from backend.app.services.execution.error_handler import (
    CircuitOpenError, ErrorHandler, LLMCallFailed, circuit_breaker,
)
from backend.app.services.execution.tracker import ExecutionControl, tracker
from backend.app.services.llm import registry
from backend.app.services.llm.base import LLMResponse
from backend.app.services.router.routing_engine import RoutingEngine

SYSTEM_PROMPT = ("You are an AI assistant helping with a multi-stage workflow. "
                 "Provide detailed, actionable output for this stage.")


class StageFailed(Exception):
    """A stage's LLM call failed on every model tried."""

    def __init__(self, message: str, attempts: list[dict]):
        super().__init__(message)
        self.attempts = attempts


def healthy_providers() -> list[str]:
    """Registered providers whose circuit breaker isn't open."""
    return [p for p in registry.list_providers() if not circuit_breaker.is_open(p)]


class _Run:
    """Per-execution settings and state shared by the stage tasks."""

    def __init__(self, workflow: Workflow, execution_id: uuid.UUID, control: ExecutionControl,
                 default_provider: str, default_model: Optional[str], use_cache: bool,
                 use_routing: bool, routing_preferences: dict[str, str], commit_progress: bool):
        self.workflow = workflow
        self.workflow_id = workflow.id
        self.execution_id = execution_id
        self.control = control
        self.default_provider = default_provider
        self.default_model = default_model
        self.use_cache = use_cache
        self.use_routing = use_routing
        self.routing_preferences = routing_preferences
        self.commit_progress = commit_progress
        self.llm_tasks: dict[uuid.UUID, asyncio.Task] = {}


class ExecutionEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.context_mgr = ContextManager(db)
        self.cache_service = SemanticCacheService(db)
        self.error_handler = ErrorHandler()
        self._db_lock = asyncio.Lock()

    async def execute_workflow(self, workflow_id: uuid.UUID,
                               default_provider: str = "gemini",
                               default_model: str | None = None,
                               use_cache: bool = True,
                               use_routing: bool = True,
                               routing_preferences: dict[str, str] | None = None,
                               parallel: bool = True,
                               execution_id: uuid.UUID | None = None,
                               commit_progress: bool = False) -> uuid.UUID:
        """
        Execute a workflow and return its execution_id.

        use_cache=False skips cache lookups (forcing fresh LLM calls) but still
        stores the new results, which refreshes the cache.
        use_routing=True lets the routing engine pick each stage's model (and a
        fallback model on failure); default_provider/default_model are used only
        when nothing can be routed. use_routing=False always uses
        stage.model_preference or default_model on default_provider.
        routing_preferences maps stage id (str) -> model_name for this execution.
        parallel=False runs one stage at a time in dependency order.
        commit_progress=True commits after every stage (background executions),
        so results become visible while the workflow is still running.
        """
        execution_id = execution_id or uuid.uuid4()

        result = await self.db.execute(
            select(Workflow)
            .options(selectinload(Workflow.stages).selectinload(Stage.dependencies))
            .where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        if not workflow.stages:
            raise ValueError("Workflow has no stages")

        analyzer = DAGAnalyzer(workflow.stages)  # raises DAGCycleError (a ValueError) on cycles
        live = await tracker.start(execution_id, workflow.id, workflow.name, analyzer.stages,
                                   analyzer.to_dict(), parallel)
        run = _Run(workflow, execution_id, live.control, default_provider, default_model, use_cache,
                   use_routing, routing_preferences or {}, commit_progress)
        print(f"[EXECUTION] {workflow.name} ({'parallel' if parallel else 'sequential'})\n{analyzer.visualize_dag()}")

        workflow.status = "running"
        for stage in workflow.stages:
            stage.status = "pending"
        await self.db.flush()
        if workflow.objective:
            await self.context_mgr.add_context(
                workflow.id, execution_id, stage_id=None,
                content=f"Workflow Objective: {workflow.objective}",
                context_type="user_input",
            )
        await self._commit_if(run)

        outcomes = await self._schedule(run, analyzer, settings.MAX_PARALLEL_STAGES if parallel else 1)

        if run.control.cancelled:
            final = "cancelled"
        elif all(outcomes.get(s.id) == "completed" for s in workflow.stages):
            final = "completed"
        else:
            final = "failed"
        async with self._db_lock:
            workflow.status = final
            await self.db.flush()
            await self._commit_if(run)
        await tracker.set_status(execution_id, final)
        print(f"[EXECUTION] {workflow.name} finished: {final}")
        return execution_id

    # ---------- scheduling ----------

    async def _schedule(self, run: _Run, analyzer: DAGAnalyzer, max_concurrency: int) -> dict[uuid.UUID, str]:
        """Start stages as their dependencies complete; returns stage_id -> outcome."""
        pending = {s.id: s for s in analyzer.stages}
        running: dict[asyncio.Task, Stage] = {}
        outcomes: dict[uuid.UUID, str] = {}
        waiter: Optional[asyncio.Task] = None

        try:
            while pending or running:
                await self._sync_pause_status(run)

                if run.control.cancelled:
                    for task in run.llm_tasks.values():
                        task.cancel()
                elif not run.control.paused:
                    ready = [
                        s for s in pending.values()
                        if all(outcomes.get(d) == "completed" for d in analyzer.nodes[s.id].dependencies)
                    ]
                    for stage in ready[:max(0, max_concurrency - len(running))]:
                        del pending[stage.id]
                        running[asyncio.create_task(self._run_stage(run, stage))] = stage

                if not running:
                    if pending and run.control.paused and not run.control.cancelled:
                        await run.control.wait_for_change()
                        continue
                    break  # finished, cancelled, or the rest is blocked by failures

                if waiter is None or waiter.done():
                    waiter = asyncio.create_task(run.control.wait_for_change())
                done, _ = await asyncio.wait([*running, waiter], return_when=asyncio.FIRST_COMPLETED)

                for task in done:
                    if task is waiter:
                        continue
                    stage = running.pop(task)
                    if task.exception() is not None:
                        print(f"[EXECUTION] Stage {stage.name} crashed: {task.exception()!r}")
                        outcomes[stage.id] = "failed"
                    else:
                        outcomes[stage.id] = task.result()
                    if outcomes[stage.id] != "completed":
                        blocked = [pending.pop(d) for d in analyzer.get_descendants(stage.id) if d in pending]
                        await self._mark_skipped(run, blocked, f"Upstream stage '{stage.name}' {outcomes[stage.id]}")
        finally:
            if waiter is not None:
                waiter.cancel()
            for task in running:  # only on unexpected errors / outer cancellation
                task.cancel()

        # Stages never started (cancelled, or dependencies unmet)
        reason = "Execution cancelled" if run.control.cancelled else "Dependencies did not complete"
        await self._mark_skipped(run, list(pending.values()), reason)
        for stage in pending.values():
            outcomes[stage.id] = "skipped"
        return outcomes

    async def _sync_pause_status(self, run: _Run) -> None:
        if run.control.cancelled:
            return
        desired = "paused" if run.control.paused else "running"
        if run.workflow.status != desired:
            async with self._db_lock:
                run.workflow.status = desired
                await self.db.flush()
                await self._commit_if(run)

    async def _mark_skipped(self, run: _Run, stages: list[Stage], reason: str) -> None:
        if not stages:
            return
        async with self._db_lock:
            for stage in stages:
                stage.status = "skipped"
            await self.db.flush()
            await self._commit_if(run)
        for stage in stages:
            await tracker.update_stage(run.execution_id, stage.id, status="skipped", error=reason)

    # ---------- one stage ----------

    async def _run_stage(self, run: _Run, stage: Stage) -> str:
        """Execute one stage; returns "completed", "failed" or "cancelled". Never raises for LLM errors."""
        started_at = datetime.now(timezone.utc)
        await tracker.update_stage(run.execution_id, stage.id, status="running")

        # --- prepare: context, embedding, cache, routing ---
        try:
            async with self._db_lock:
                stage.status = "running"
                await self.db.flush()
                stage_input = await self.context_mgr.assemble_stage_input(run.workflow_id, run.execution_id, stage)
            embedding = await self._embed(stage, stage_input)  # network call: outside the lock
            async with self._db_lock:
                prepared = await self._prepare_stage(run, stage, stage_input, embedding)
        except Exception as e:
            async with self._db_lock:
                await self._record_failure(run.workflow_id, run.execution_id, stage,
                                           f"Stage preparation failed: {e}", started_at)
                await self._commit_if(run)
            await tracker.update_stage(run.execution_id, stage.id, status="failed", error=str(e))
            return "failed"

        if isinstance(prepared, CacheHitResponse):
            await tracker.update_stage(run.execution_id, stage.id, status="completed", cache_hit=True,
                                       provider="cache", model=prepared.entry.model_used)
            return "completed"
        provider_name, model, routing_info = prepared

        await tracker.update_stage(run.execution_id, stage.id, provider=provider_name, model=model)

        # --- LLM call: runs concurrently; cancellable via run.control ---
        if run.control.cancelled:
            return await self._finish_cancelled(run, stage, started_at)
        llm_task = asyncio.create_task(self._call_llm(run, stage, stage_input, provider_name, model))
        run.llm_tasks[stage.id] = llm_task
        try:
            response, attempts, fallback = await llm_task
        except asyncio.CancelledError:
            if llm_task.cancelled() and run.control.cancelled:
                return await self._finish_cancelled(run, stage, started_at)
            raise  # the engine itself is being cancelled
        except Exception as e:
            attempts = getattr(e, "attempts", [])
            async with self._db_lock:
                await self._record_failure(run.workflow_id, run.execution_id, stage, str(e), started_at,
                                           metadata={"routing": routing_info, "attempts": attempts})
                await self._commit_if(run)
            await tracker.update_stage(run.execution_id, stage.id, status="failed", error=str(e))
            return "failed"
        finally:
            run.llm_tasks.pop(stage.id, None)

        if fallback:
            routing_info = {**(routing_info or {"routed": run.use_routing}), "was_fallback": True,
                            "reason": fallback["reason"], "fallback_from": fallback["from"]}

        # --- finalize: context, cache, record (database work, serialized) ---
        async with self._db_lock:
            await self.context_mgr.add_context(
                run.workflow_id, run.execution_id, stage.id,
                content=response.content, context_type="stage_output",
                token_count=response.total_tokens,
            )
            if embedding is not None:
                await self._cache_store(run.workflow_id, run.execution_id, stage, stage_input, response, embedding)
            metadata = {}
            if routing_info:
                metadata["routing"] = routing_info
            if attempts:
                metadata["attempts"] = attempts
            self.db.add(ExecutionRecord(
                workflow_id=run.workflow_id, stage_id=stage.id, execution_id=run.execution_id,
                model_used=response.model, provider=response.provider,
                input_tokens=response.input_tokens, output_tokens=response.output_tokens,
                latency_ms=response.latency_ms, estimated_cost=response.estimated_cost,
                status="completed", result=response.content, cache_hit=False,
                started_at=started_at, completed_at=datetime.now(timezone.utc),
                metadata_=metadata,
            ))
            stage.status = "completed"
            await self.db.flush()
            await self._commit_if(run)

        await tracker.update_stage(run.execution_id, stage.id, status="completed",
                                   provider=response.provider, model=response.model)
        return "completed"

    async def _embed(self, stage: Stage, stage_input: str) -> Optional[list[float]]:
        """Embedding of the stage input, shared by cache lookup and store; None if unavailable."""
        try:
            return await self.cache_service.embedding_service.generate_embedding(stage_input)
        except Exception as e:
            print(f"[CACHE WARN] Embedding failed for stage {stage.name}, cache skipped: {e}")
            return None

    async def _prepare_stage(self, run: _Run, stage: Stage, stage_input: str,
                             embedding: Optional[list[float]]):
        """
        Try the cache, else pick the model. Lock must be held.
        Returns the CacheHitResponse on a hit, else (provider, model, routing_info).
        """
        if run.use_cache and embedding is not None:
            cache_result = await self._cache_lookup(run.workflow_id, run.execution_id, stage, stage_input, embedding)
            if cache_result.cache_hit and cache_result.entry:
                print(f"[CACHE HIT] Stage {stage.name} - Similarity: {cache_result.similarity_score:.4f}")
                await self._record_cache_hit(run.workflow_id, run.execution_id, stage, cache_result)
                await self._commit_if(run)
                return cache_result

        print(f"[CACHE MISS] Stage {stage.name} - Executing with LLM")
        user_override = run.routing_preferences.get(str(stage.id))
        if run.use_routing:
            provider_name, model, routing_info = await self._route(
                run.execution_id, stage, run.default_provider, run.default_model, user_override
            )
        else:
            provider_name = run.default_provider
            model = user_override or stage.model_preference or run.default_model
            routing_info = None
        return provider_name, model, routing_info

    async def _call_llm(self, run: _Run, stage: Stage, stage_input: str, provider_name: str,
                        model: Optional[str]) -> tuple[LLMResponse, list[dict], Optional[dict]]:
        """
        Call the chosen model with retries; if it fails (or its circuit is open) and routing
        is on, ask the router for one fallback model. Returns (response, failed_attempts, fallback_info).
        """
        try:
            provider = registry.get(provider_name)
            model = model or provider.get_default_model()
            response, attempts = await self.error_handler.call(provider, stage_input, model, SYSTEM_PROMPT)
            return response, attempts, None
        except (LLMCallFailed, CircuitOpenError, ValueError) as e:
            attempts = list(getattr(e, "attempts", []))
            failure = str(e)
            if not run.use_routing:
                raise StageFailed(failure, attempts) from e

        async with self._db_lock:
            router = RoutingEngine(self.db, available_providers=healthy_providers())
            async with self.db.begin_nested():
                fallback = await router.select_fallback_model(
                    stage, run.execution_id, exclude={(provider_name, model)}, failure=failure
                )
        if fallback is None:
            raise StageFailed(f"{failure}; no fallback model available", attempts)

        print(f"[FALLBACK] Stage {stage.name}: {provider_name}/{model} -> {fallback.provider}/{fallback.model_name}")
        await tracker.update_stage(run.execution_id, stage.id, provider=fallback.provider, model=fallback.model_name)
        try:
            response, more = await self.error_handler.call(
                registry.get(fallback.provider), stage_input, fallback.model_name, SYSTEM_PROMPT
            )
        except (LLMCallFailed, CircuitOpenError) as e:
            raise StageFailed(f"{failure}; fallback also failed: {e}",
                              attempts + list(getattr(e, "attempts", []))) from e
        return response, attempts + more, {
            "from": f"{provider_name}/{model}",
            "reason": f"Fallback after failure: {failure}"[:500],
        }

    async def _finish_cancelled(self, run: _Run, stage: Stage, started_at: datetime) -> str:
        async with self._db_lock:
            self.db.add(ExecutionRecord(
                workflow_id=run.workflow_id, stage_id=stage.id, execution_id=run.execution_id,
                status="cancelled", error_message="Cancelled by user",
                started_at=started_at, completed_at=datetime.now(timezone.utc),
            ))
            stage.status = "skipped"
            await self.db.flush()
            await self._commit_if(run)
        await tracker.update_stage(run.execution_id, stage.id, status="cancelled", error="Cancelled by user")
        return "cancelled"

    async def _commit_if(self, run: _Run) -> None:
        if run.commit_progress:
            await self.db.commit()

    # ---------- helpers (called with the lock held) ----------

    async def _route(self, execution_id: uuid.UUID, stage: Stage, default_provider: str,
                     default_model: str | None, user_override: str | None
                     ) -> tuple[str, str | None, dict]:
        """
        Ask the router for this stage's model; returns (provider, model, routing_info).
        Falls back to the execution defaults when nothing is routable or routing errors,
        logging that as a fallback decision too.
        """
        router = RoutingEngine(self.db, available_providers=healthy_providers())
        try:
            async with self.db.begin_nested():
                profile, reason = await router.select_model_for_stage(stage, execution_id, user_override=user_override)
        except Exception as e:
            profile, reason = None, f"Routing error: {e}"

        if profile:
            print(f"[ROUTER] Stage {stage.name} -> {profile.provider}/{profile.model_name} ({reason})")
            decision = router.last_decision
            return profile.provider, profile.model_name, {
                "routed": True,
                "reason": reason,
                "decision_id": str(decision.id),
                "was_user_override": decision.was_user_override,
                "was_fallback": decision.was_fallback,
            }

        model = user_override or stage.model_preference or default_model
        reason = f"{reason}; using execution default {default_provider}/{model or 'provider default'}"
        print(f"[ROUTER] Stage {stage.name} -> {reason}")
        try:
            async with self.db.begin_nested():
                await router.log_decision(execution_id, stage, default_provider,
                                          model or "provider default", reason, was_fallback=True)
        except Exception as e:
            print(f"[ROUTER WARN] Could not log decision for stage {stage.name}: {e}")
        return default_provider, model, {"routed": False, "reason": reason,
                                         "was_user_override": False, "was_fallback": True}

    async def _cache_lookup(self, workflow_id: uuid.UUID, execution_id: uuid.UUID,
                            stage: Stage, stage_input: str, embedding: list[float]) -> CacheHitResponse:
        """
        Best-effort cache lookup. Any failure (e.g. embedding API unavailable) is
        treated as a miss; the savepoint keeps a failed query from aborting the
        surrounding transaction.
        """
        try:
            async with self.db.begin_nested():
                return await self.cache_service.lookup_with_validation(
                    input_text=stage_input,
                    workflow_id=workflow_id,
                    execution_id=execution_id,
                    current_stage=stage,
                    embedding=embedding,
                )
        except Exception as e:
            print(f"[CACHE WARN] Lookup failed for stage {stage.name}: {e}")
            return CacheHitResponse(cache_hit=False)

    async def _cache_store(self, workflow_id: uuid.UUID, execution_id: uuid.UUID,
                           stage: Stage, stage_input: str, response: LLMResponse,
                           embedding: list[float]) -> None:
        """Best-effort cache store; a failure never fails the stage."""
        try:
            async with self.db.begin_nested():
                await self.cache_service.store_with_dependencies(
                    input_text=stage_input,
                    result=response.content,
                    workflow_id=workflow_id,
                    execution_id=execution_id,
                    current_stage=stage,
                    result_tokens=response.total_tokens,
                    model_used=response.model,
                    embedding=embedding,
                )
        except Exception as e:
            print(f"[CACHE WARN] Store failed for stage {stage.name}: {e}")

    async def _record_cache_hit(self, workflow_id: uuid.UUID, execution_id: uuid.UUID,
                                stage: Stage, cache_result: CacheHitResponse) -> ExecutionRecord:
        """Record a stage served from cache: no LLM call, so zero tokens, latency and cost."""
        entry = cache_result.entry
        now = datetime.now(timezone.utc)

        await self.context_mgr.add_context(
            workflow_id, execution_id, stage.id,
            content=entry.result, context_type="stage_output",
            token_count=entry.result_tokens,
        )

        record = ExecutionRecord(
            workflow_id=workflow_id, stage_id=stage.id, execution_id=execution_id,
            model_used=entry.model_used, provider="cache",
            input_tokens=0, output_tokens=0, latency_ms=0, estimated_cost=0,
            status="completed", result=entry.result, cache_hit=True,
            started_at=now, completed_at=now,
            metadata_={
                "cache_entry_id": str(entry.id),
                "similarity_score": cache_result.similarity_score,
                "tokens_saved": cache_result.tokens_saved,
                "cost_saved": float(cache_result.cost_saved or 0),
            },
        )
        self.db.add(record)
        stage.status = "completed"
        await self.db.flush()

        return record

    async def _record_failure(self, workflow_id: uuid.UUID, execution_id: uuid.UUID,
                              stage: Stage, error_msg: str, started_at: datetime | None = None,
                              metadata: dict | None = None):
        record = ExecutionRecord(
            workflow_id=workflow_id, stage_id=stage.id, execution_id=execution_id,
            status="failed", error_message=error_msg,
            started_at=started_at or datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            metadata_={k: v for k, v in (metadata or {}).items() if v},
        )
        self.db.add(record)
        stage.status = "failed"
        await self.db.flush()
