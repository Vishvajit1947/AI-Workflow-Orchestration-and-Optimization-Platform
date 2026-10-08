# MT-19 — Semantic Cache Model & Service - COMPLETION SUMMARY

## 🎯 Status: COMPLETE ✅

**Completion Date**: September 27, 2026  
**Task**: Semantic Cache Model & Service (Phase 3)  
**Result**: `cache_entries` table with pgvector IVFFlat cosine index, `SemanticCacheService` for lookup/store/invalidate/expire, Pydantic schemas, and a passing test suite.

---

## 📊 Implementation Overview

### 1. ORM Model (`backend/app/models/cache.py`)
- `CacheEntry` with `input_embedding: Vector(1536)`, optional FKs to `workflows` / `stages` (`ON DELETE CASCADE`), `dependency_hash`, `hit_count`, `similarity_threshold`, `is_valid`, `created_at`, `expires_at`.
- B-tree indexes on `stage_type`, `is_valid`, `created_at`.
- The IVFFlat vector index is created in the migration (not the model), since `Index(..., postgresql_using="ivfflat")` is unreliable with `postgresql_ops`.
- Registered in `backend/app/models/__init__.py`.

### 2. Migration (`backend/alembic/versions/e431515b2d0f_create_cache_entries_table.py`)
- Revises `0bb186599c66` (enable pgvector).
- Creates the table, B-tree indexes, and `idx_cache_entries_embedding` (`ivfflat (input_embedding vector_cosine_ops) WITH (lists = 100)`).
- Downgrade drops indexes and table.

### 3. Schemas (`backend/app/schemas/cache.py`)
- `CacheEntryCreate`, `CacheEntryResponse`, `CacheHitResponse`, `CacheStats`.

### 4. Service (`backend/app/services/cache/semantic_cache.py`)
- `lookup()` — embeds input, filters by `is_valid`, not expired, similarity `>= threshold` (`1 - cosine_distance`), optional `stage_type` / `dependency_hash`; returns best match and increments `hit_count`.
- `store()` — embeds input, applies optional TTL, persists entry.
- `invalidate()` — marks entries invalid by workflow / stage / stage type.
- `clear_expired()` — marks expired entries invalid.
- `compute_dependency_hash()` — SHA-256 of upstream outputs.
- Threshold configurable via `CACHE_SIMILARITY_THRESHOLD` (default `0.92`) or per-call override.

### 5. Tests (`backend/tests/test_semantic_cache.py`)
- Store & lookup, semantic similarity, miss on unrelated input, invalidation, hit-count increment, dependency hash, cost estimate.
- Embedding service is mocked (deterministic 1536-dim vectors), so tests don't need an OpenAI key.

### 6. Test isolation fix (`backend/tests/conftest.py`)
- The `engine` fixture runs `Base.metadata.drop_all` on teardown and was pointed at the **dev** database, which wiped the migrated schema (including `cache_entries`) after every test run.
- Tests now use `ai_orchestrator_test` (overridable via `TEST_DATABASE_URL`), and the fixture ensures the `vector` extension exists before `create_all`.
- One-time setup:
  ```powershell
  docker exec ai_orchestrator_postgres psql -U orchestrator -d ai_orchestrator -c "CREATE DATABASE ai_orchestrator_test;"
  docker exec ai_orchestrator_postgres psql -U orchestrator -d ai_orchestrator_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
  ```

---

## 🧪 Verification Results

### Test 1: Migration
Dev schema had been dropped by earlier test runs, so it was rebuilt:
```powershell
cd backend
python -m alembic stamp base
python -m alembic upgrade head
```
```
Running upgrade  -> 001, initial_tables_workflows_stages_dependencies
Running upgrade 001 -> f9282f3834c7, add_context_and_execution_tables
Running upgrade f9282f3834c7 -> d24f57e3758d, add_execution_indexes_and_relationships
Running upgrade d24f57e3758d -> 0bb186599c66, enable_pgvector_extension
Running upgrade 0bb186599c66 -> e431515b2d0f, create_cache_entries_table
```

### Test 2: Table structure
```powershell
docker exec ai_orchestrator_postgres psql -U orchestrator -d ai_orchestrator -c "\d cache_entries"
```
```
 input_embedding      | vector(1536)             |           | not null |
 ...
Indexes:
    "cache_entries_pkey" PRIMARY KEY, btree (id)
    "idx_cache_entries_created_at" btree (created_at)
    "idx_cache_entries_embedding" ivfflat (input_embedding vector_cosine_ops) WITH (lists='100')
    "idx_cache_entries_is_valid" btree (is_valid)
    "idx_cache_entries_stage_type" btree (stage_type)
```

### Test 3: Cache tests
```powershell
python -m pytest backend/tests/test_semantic_cache.py -v
```
```
test_cache_store_and_lookup PASSED
test_cache_semantic_similarity PASSED
test_cache_miss_on_different_text PASSED
test_cache_invalidation PASSED
test_hit_count_increment PASSED
test_compute_dependency_hash PASSED
test_estimate_cost_saved PASSED
7 passed
```
Dev tables were confirmed intact after the full suite ran.

---

## ⚠️ Known Pre-existing Issues (not part of MT-19)
- `tests/test_executions.py` imports `from app.models ...` and fails to collect when run from the repo root.
- `tests/test_llm_providers.py` passes `api_key=` to provider constructors that don't accept it (5 failures).
- `tests/test_phase2_integration.py` patches `OpenAIProvider.generate`, but with no `OPENAI_API_KEY` set the engine routes to another provider, so workflows fail (6 failures).

---

## ✅ Acceptance Checklist
- [x] `CacheEntry` model created with vector column.
- [x] Alembic migration creates `cache_entries` table with vector index.
- [x] `SemanticCacheService.lookup()` performs cosine similarity search.
- [x] `SemanticCacheService.store()` saves cache entries with embeddings.
- [x] Cache hit increments `hit_count`.
- [x] Similarity threshold is configurable.
- [x] Cache invalidation marks entries as invalid.
- [x] Expired entries can be cleared.
- [x] Dependency hash computed for cache validation.
- [x] All cache tests pass.

## ➡️ Next
**MT-20 — Workflow-Aware Cache Validation**
