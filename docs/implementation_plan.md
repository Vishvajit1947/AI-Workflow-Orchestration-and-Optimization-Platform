# AI Workflow Orchestration and Optimization Platform — Phased Implementation Plan

## Project Overview

Build a full-stack **AI Workflow Orchestration and Optimization Platform** that manages multi-stage AI workflows using multiple LLMs. The platform maintains workflow context, reuses semantically similar results via caching, selects appropriate LLMs per stage, executes dependent workflows efficiently, and provides performance analytics — all differentiated from basic LLM gateways by its **workflow-level** optimization approach.

> [!IMPORTANT]
> This plan is divided into **6 phases**, each independently deployable and testable. Completing each phase gives you a working increment that you can demo. Phases build on each other sequentially.

---

## Technology Stack (Prerequisites)

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **Frontend** | React 18+, TypeScript, Tailwind CSS, Vite |
| **Database** | PostgreSQL 15+ |
| **Cache / Vector Storage** | Redis 7+, pgvector (PostgreSQL extension) |
| **LLM Providers** | OpenAI, Anthropic (Claude), Google Gemini |
| **Embeddings** | OpenAI `text-embedding-3-small` or Sentence-Transformers (local) |
| **DevOps** | Git/GitHub, Docker, Docker Compose |
| **Testing** | pytest (backend), React Testing Library + Vitest (frontend) |

### Environment Prerequisites

Before starting any phase, ensure you have:
- [ ] Python 3.11+ installed
- [ ] Node.js 18+ and npm installed
- [ ] PostgreSQL 15+ running locally or via Docker
- [ ] Redis 7+ running locally or via Docker
- [ ] Docker & Docker Compose installed
- [ ] At least one LLM API key (OpenAI recommended to start)
- [ ] Git initialized repository

---

## Phase 1: Project Foundation & Workflow Manager (Core CRUD)

### 🎯 Goal
Set up the full-stack project skeleton with a functional **Workflow Manager** — users can create, configure, read, update, and delete workflows and their stages through API and a basic UI.

### 📋 Requirements

| ID | Requirement | Priority |
|---|---|---|
| P1-R1 | Project scaffolding: FastAPI backend + React frontend + Docker Compose | Must |
| P1-R2 | Database schema: workflows, stages, stage dependencies | Must |
| P1-R3 | Workflow CRUD API (create, read, update, delete workflows) | Must |
| P1-R4 | Stage CRUD API (add/edit/remove/reorder stages within a workflow) | Must |
| P1-R5 | Stage dependency management (sequential, independent, merge) | Must |
| P1-R6 | Stage configuration (instructions, model preferences, order) | Must |
| P1-R7 | Workflow validation (dependency cycles, missing stages) | Must |
| P1-R8 | Basic React UI: workflow list, create/edit workflow, stage editor | Must |
| P1-R9 | API documentation (auto-generated Swagger/OpenAPI) | Must |
| P1-R10 | Environment configuration (.env, settings management) | Must |

### 🏗️ Deliverables

#### Backend (`/backend`)

```
backend/
├── app/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings & env management
│   ├── database.py                # SQLAlchemy engine & session
│   ├── models/
│   │   ├── __init__.py
│   │   ├── workflow.py            # Workflow ORM model
│   │   └── stage.py               # Stage ORM model + dependencies
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── workflow.py            # Pydantic schemas for workflow
│   │   └── stage.py               # Pydantic schemas for stage
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── workflow.py            # Workflow CRUD endpoints
│   │   └── stage.py               # Stage CRUD endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   └── workflow_manager.py    # Workflow business logic
│   └── utils/
│       ├── __init__.py
│       └── validators.py          # Dependency cycle detection, etc.
├── alembic/                       # Database migrations
├── tests/
│   ├── test_workflows.py
│   └── test_stages.py
├── requirements.txt
├── Dockerfile
└── alembic.ini
```

#### Frontend (`/frontend`)

```
frontend/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── api/
│   │   └── client.ts              # Axios/fetch wrapper
│   ├── pages/
│   │   ├── WorkflowList.tsx       # List all workflows
│   │   ├── WorkflowEditor.tsx     # Create/edit workflow + stages
│   │   └── WorkflowDetail.tsx     # View workflow details
│   ├── components/
│   │   ├── StageEditor.tsx        # Stage configuration form
│   │   ├── DependencyGraph.tsx    # Visual dependency graph
│   │   └── Layout.tsx             # App shell/layout
│   └── types/
│       └── index.ts               # TypeScript type definitions
├── package.json
├── vite.config.ts
├── Dockerfile
└── tsconfig.json
```

#### Infrastructure

```
docker-compose.yml                 # PostgreSQL, Redis, backend, frontend
.env.example                       # Template environment variables
README.md                          # Setup instructions
```

### 📐 Database Schema

```sql
-- workflows table
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    objective TEXT,
    status VARCHAR(50) DEFAULT 'draft',  -- draft, running, completed, failed, paused
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- stages table
CREATE TABLE stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    instruction TEXT NOT NULL,
    stage_order INTEGER NOT NULL,
    stage_type VARCHAR(100),  -- analysis, design, generation, testing, etc.
    model_preference VARCHAR(100),  -- preferred LLM model
    config JSONB DEFAULT '{}',  -- additional stage configuration
    status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed, skipped
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- stage_dependencies table
CREATE TABLE stage_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_id UUID REFERENCES stages(id) ON DELETE CASCADE,
    depends_on_stage_id UUID REFERENCES stages(id) ON DELETE CASCADE,
    dependency_type VARCHAR(50) DEFAULT 'sequential',  -- sequential, merge
    UNIQUE(stage_id, depends_on_stage_id)
);
```

### 🧪 Test Cases

| Test ID | Test Case | Expected Result |
|---|---|---|
| P1-T1 | Create a workflow with name and description | Returns 201 with workflow object |
| P1-T2 | Create a workflow without required `name` field | Returns 422 validation error |
| P1-T3 | Get all workflows (paginated) | Returns list with pagination metadata |
| P1-T4 | Get single workflow by ID | Returns workflow with all stages |
| P1-T5 | Update workflow name | Returns 200 with updated workflow |
| P1-T6 | Delete workflow | Cascades deletes stages, returns 204 |
| P1-T7 | Add 5 stages to a workflow with ordering | All stages created with correct order |
| P1-T8 | Set dependency: Stage 2 depends on Stage 1 | Dependency created successfully |
| P1-T9 | Create circular dependency (Stage 1→2→3→1) | Returns 400 with cycle detection error |
| P1-T10 | Reorder stages in a workflow | Stage order updated correctly |
| P1-T11 | Delete a stage that others depend on | Returns 400 or cascades dependency removal |
| P1-T12 | Validate workflow with no stages | Returns validation warning |
| P1-T13 | Frontend: Create workflow form renders | Form visible with name, description, objective |
| P1-T14 | Frontend: Stage editor drag-to-reorder | Stages reorder and save correctly |

### ✅ Phase 1 Completion Criteria
- [ ] `docker-compose up` starts the full stack (backend, frontend, postgres, redis)
- [ ] All workflow and stage CRUD endpoints work via Swagger
- [ ] Frontend can create a workflow, add stages, set dependencies
- [ ] Dependency cycle detection prevents invalid workflows
- [ ] All 14 test cases pass

---

## Phase 2: Workflow Context Management & LLM Integration

### 🎯 Goal
Implement **Workflow Context** that tracks state across stages, build the **LLM provider abstraction** to support multiple LLMs, and enable basic **sequential workflow execution** (without caching or routing — just run stages in order using a configured model).

### 📋 Requirements

| ID | Requirement | Priority |
|---|---|---|
| P2-R1 | Workflow Context data model (stores outputs, state, metadata per stage) | Must |
| P2-R2 | Context Management service (add, retrieve, select relevant context) | Must |
| P2-R3 | Relevant context selection (avoid sending entire history to every LLM) | Must |
| P2-R4 | Stage Input assembly: `Stage Instruction + Relevant Previous Outputs + Context` | Must |
| P2-R5 | LLM Provider abstraction (unified interface for all providers) | Must |
| P2-R6 | OpenAI provider implementation | Must |
| P2-R7 | Anthropic (Claude) provider implementation | Should |
| P2-R8 | Google Gemini provider implementation | Should |
| P2-R9 | Provider configuration (API keys, model names, defaults) | Must |
| P2-R10 | Basic sequential Execution Engine (run stages one by one) | Must |
| P2-R11 | Workflow execution API endpoint (`POST /workflows/{id}/execute`) | Must |
| P2-R12 | Execution status tracking (pending → running → completed/failed) | Must |
| P2-R13 | Basic error handling (LLM timeout, rate limit, network failure) | Must |
| P2-R14 | Retry mechanism with configurable attempts | Should |
| P2-R15 | Stage execution result storage in database | Must |
| P2-R16 | Frontend: Workflow execution trigger and status display | Must |
| P2-R17 | Frontend: View stage outputs after execution | Must |

### 🏗️ New/Modified Files

```
backend/app/
├── models/
│   ├── context.py                 # WorkflowContext ORM model
│   └── execution.py               # ExecutionRecord ORM model
├── schemas/
│   ├── context.py                 # Context Pydantic schemas
│   └── execution.py               # Execution Pydantic schemas
├── services/
│   ├── context_manager.py         # Context CRUD + relevant selection
│   ├── execution_engine.py        # Sequential stage execution
│   └── llm/
│       ├── __init__.py
│       ├── base.py                # Abstract LLM provider interface
│       ├── openai_provider.py     # OpenAI implementation
│       ├── anthropic_provider.py  # Anthropic implementation
│       ├── gemini_provider.py     # Gemini implementation
│       └── provider_registry.py   # Provider registration & lookup
├── routers/
│   └── execution.py               # Execution endpoints
└── tests/
    ├── test_context.py
    ├── test_execution.py
    └── test_llm_providers.py
```

### 📐 Database Schema Additions

```sql
-- workflow_context table
CREATE TABLE workflow_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    execution_id UUID,  -- links to a specific execution run
    stage_id UUID REFERENCES stages(id),
    content TEXT NOT NULL,  -- the actual output/result
    context_type VARCHAR(50),  -- 'stage_output', 'user_input', 'system'
    token_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- execution_records table
CREATE TABLE execution_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    stage_id UUID REFERENCES stages(id),
    execution_id UUID NOT NULL,  -- groups all stages of one run
    model_used VARCHAR(100),
    provider VARCHAR(50),
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER,
    estimated_cost DECIMAL(10,6),
    status VARCHAR(50),  -- pending, running, completed, failed
    error_message TEXT,
    result TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 🧪 Test Cases

| Test ID | Test Case | Expected Result |
|---|---|---|
| P2-T1 | Execute a 3-stage workflow sequentially | All 3 stages complete in order |
| P2-T2 | Stage 2 receives Stage 1's output as context | Stage 2 input includes Stage 1 output |
| P2-T3 | Context selection returns only relevant previous outputs (not entire history) | Token count is reduced vs sending everything |
| P2-T4 | Execute with invalid API key | Returns error with appropriate message |
| P2-T5 | Execute with LLM timeout (mocked) | Retry mechanism triggers, then fails gracefully |
| P2-T6 | Switch LLM provider for a stage | Stage uses the specified provider |
| P2-T7 | OpenAI provider returns structured response | Response parsed and stored correctly |
| P2-T8 | Anthropic provider returns structured response | Response parsed and stored correctly |
| P2-T9 | Execution status updates in real-time | Status changes from pending → running → completed |
| P2-T10 | View execution results via API | Returns all stage outputs for an execution |
| P2-T11 | Rate limit handling (429 response, mocked) | Waits and retries with backoff |
| P2-T12 | Frontend: Click "Execute" on a workflow | Execution starts, status updates live |
| P2-T13 | Frontend: View each stage's output after execution | All outputs visible with model info |

### ✅ Phase 2 Completion Criteria
- [ ] Can execute a multi-stage workflow end-to-end with at least 1 LLM provider
- [ ] Context flows correctly from stage to stage (only relevant context)
- [ ] Execution records are stored with latency, tokens, cost, model info
- [ ] Error handling and retries work for LLM failures
- [ ] Frontend shows execution trigger, progress, and results
- [ ] All 13 test cases pass

---

## Phase 3: Semantic Caching & Embeddings

### 🎯 Goal
Implement **Semantic Caching** with **embeddings and similarity search** so that previously computed stage results can be reused when new inputs are semantically similar. This is the core optimization feature that differentiates from basic LLM gateways.

### 📋 Requirements

| ID | Requirement | Priority |
|---|---|---|
| P3-R1 | Embedding generation service (convert stage input text → vector) | Must |
| P3-R2 | Vector storage setup (pgvector extension in PostgreSQL) | Must |
| P3-R3 | Similarity search (cosine similarity against stored embeddings) | Must |
| P3-R4 | Configurable similarity threshold for cache hits | Must |
| P3-R5 | Cache lookup before every LLM execution | Must |
| P3-R6 | Cache storage after every LLM execution | Must |
| P3-R7 | Cache hit → return cached result (skip LLM call) | Must |
| P3-R8 | Cache miss → proceed to router/execution | Must |
| P3-R9 | **Workflow-aware caching**: consider stage type, dependency versions | Must |
| P3-R10 | Dependency-aware cache invalidation (stale if upstream changed) | Must |
| P3-R11 | Cache management API (view, clear, configure threshold) | Should |
| P3-R12 | Cache hit/miss logging for analytics | Must |
| P3-R13 | Frontend: Cache hit/miss indicators on execution results | Should |
| P3-R14 | Frontend: Cache management page (view cached entries, clear cache) | Should |

### 🏗️ New/Modified Files

```
backend/app/
├── services/
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── embedding_service.py   # Generate embeddings via API or local model
│   │   ├── semantic_cache.py      # Cache lookup, store, invalidate
│   │   ├── similarity.py          # Cosine similarity + threshold logic
│   │   └── cache_validator.py     # Workflow-aware validity checks
│   └── execution_engine.py        # MODIFIED: add cache check before LLM call
├── models/
│   └── cache.py                   # CacheEntry ORM model
├── schemas/
│   └── cache.py                   # Cache Pydantic schemas
├── routers/
│   └── cache.py                   # Cache management endpoints
└── tests/
    ├── test_embedding.py
    ├── test_semantic_cache.py
    └── test_cache_invalidation.py
```

### 📐 Database Schema Additions

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- cache_entries table
CREATE TABLE cache_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id),
    stage_id UUID REFERENCES stages(id),
    stage_type VARCHAR(100),
    input_text TEXT NOT NULL,
    input_embedding vector(1536),  -- embedding vector dimension
    result TEXT NOT NULL,
    result_tokens INTEGER,
    model_used VARCHAR(100),
    dependency_hash VARCHAR(64),  -- hash of upstream dependency outputs
    hit_count INTEGER DEFAULT 0,
    similarity_threshold DECIMAL(4,3) DEFAULT 0.92,
    is_valid BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Create index for fast similarity search
CREATE INDEX ON cache_entries USING ivfflat (input_embedding vector_cosine_ops) WITH (lists = 100);
```

### 🔄 Execution Flow (Updated)

```
Stage Input Assembled
    ↓
Generate Embedding of Stage Input
    ↓
Search cache_entries WHERE:
  - same stage_type
  - cosine_similarity(input_embedding, stored_embedding) >= threshold
  - dependency_hash matches (workflow-aware check)
  - is_valid = true
    ↓
Cache Hit?
  YES → Return cached result, log cache_hit, increment hit_count
  NO  → Proceed to LLM execution, store result + embedding in cache
```

### 🧪 Test Cases

| Test ID | Test Case | Expected Result |
|---|---|---|
| P3-T1 | Generate embedding for a text prompt | Returns 1536-dim float vector |
| P3-T2 | Store cache entry with embedding | Entry stored with valid vector |
| P3-T3 | Identical prompt → cache hit | Returns cached result, no LLM call |
| P3-T4 | Semantically similar prompt (reworded) → cache hit | Similarity ≥ threshold, cached result returned |
| P3-T5 | Semantically different prompt → cache miss | Similarity < threshold, LLM executes |
| P3-T6 | Cache hit with stale dependency (upstream output changed) → cache miss | Dependency hash mismatch, result marked invalid |
| P3-T7 | Execute same workflow twice → second run uses cache | Second execution faster, cache hits logged |
| P3-T8 | Clear cache for a workflow | All entries removed, next run executes fresh |
| P3-T9 | Configure similarity threshold to 0.99 (very strict) | Fewer cache hits, more LLM calls |
| P3-T10 | Configure similarity threshold to 0.80 (lenient) | More cache hits, verify quality acceptable |
| P3-T11 | Cache entry with expired TTL → cache miss | Expired entries skipped |
| P3-T12 | Frontend: Cache hit shows green indicator, miss shows orange | Visual indicators correct |
| P3-T13 | API: GET /cache/entries returns all cached data | Returns list with similarity scores |

### ✅ Phase 3 Completion Criteria
- [ ] Embeddings generated for all stage inputs
- [ ] Semantic similarity search works with pgvector
- [ ] Cache hits skip LLM calls and return stored results
- [ ] Workflow-aware invalidation prevents stale cache reuse
- [ ] Re-running a workflow is measurably faster (cache hits)
- [ ] All 13 test cases pass

---

## Phase 4: Stage-Aware Routing

### 🎯 Goal
Implement the **Stage-Aware Router** that intelligently selects the best LLM for each stage based on stage type, model capabilities, latency requirements, cost considerations, and user preferences.

### 📋 Requirements

| ID | Requirement | Priority |
|---|---|---|
| P4-R1 | Model registry (register available models with capabilities & pricing) | Must |
| P4-R2 | Model capability profiles (speed, quality, cost, context window, strengths) | Must |
| P4-R3 | Stage-to-model matching algorithm | Must |
| P4-R4 | Routing rules configuration (per-stage or per-stage-type) | Must |
| P4-R5 | Cost-based routing (prefer cheaper models for simpler stages) | Should |
| P4-R6 | Latency-based routing (prefer faster models when speed matters) | Should |
| P4-R7 | Fallback model selection (if primary model unavailable) | Must |
| P4-R8 | User override (manually specify model for a stage) | Must |
| P4-R9 | Routing decision logging for analytics | Must |
| P4-R10 | Frontend: Model selection UI with auto-recommendation | Should |
| P4-R11 | Frontend: Routing configuration page | Should |

### 🏗️ New/Modified Files

```
backend/app/
├── services/
│   ├── router/
│   │   ├── __init__.py
│   │   ├── model_registry.py      # Available models & capabilities
│   │   ├── routing_engine.py      # Stage-aware routing algorithm
│   │   ├── routing_rules.py       # Configurable routing rules
│   │   └── cost_calculator.py     # Cost estimation per model
│   └── execution_engine.py        # MODIFIED: use router before execution
├── models/
│   └── routing.py                 # RoutingConfig, ModelProfile ORM
├── schemas/
│   └── routing.py                 # Routing Pydantic schemas
├── routers/
│   └── routing.py                 # Routing config endpoints
└── tests/
    ├── test_routing_engine.py
    └── test_model_registry.py
```

### 📐 Database Schema Additions

```sql
-- model_profiles table
CREATE TABLE model_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,  -- openai, anthropic, google
    model_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(100),
    capabilities JSONB DEFAULT '{}',  -- {analysis: 0.9, generation: 0.95, ...}
    max_context_tokens INTEGER,
    cost_per_input_token DECIMAL(10,8),
    cost_per_output_token DECIMAL(10,8),
    avg_latency_ms INTEGER,
    is_available BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(provider, model_name)
);

-- routing_rules table
CREATE TABLE routing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_type VARCHAR(100),  -- analysis, design, generation, testing, etc.
    priority_factor VARCHAR(50) DEFAULT 'balanced',  -- cost, speed, quality, balanced
    preferred_model_id UUID REFERENCES model_profiles(id),
    fallback_model_id UUID REFERENCES model_profiles(id),
    max_cost_per_call DECIMAL(10,4),
    max_latency_ms INTEGER,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- routing_decisions table (for analytics)
CREATE TABLE routing_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID,
    stage_id UUID REFERENCES stages(id),
    stage_type VARCHAR(100),
    selected_model VARCHAR(100),
    selected_provider VARCHAR(50),
    selection_reason TEXT,  -- why this model was chosen
    alternatives_considered JSONB,  -- other models evaluated
    was_user_override BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 🧪 Test Cases

| Test ID | Test Case | Expected Result |
|---|---|---|
| P4-T1 | Router selects model for "analysis" stage type | Returns appropriate analysis-capable model |
| P4-T2 | Router selects model for "code_generation" stage type | Returns code-strong model (e.g., Claude) |
| P4-T3 | Cost-priority routing picks cheaper model | Cheapest capable model selected |
| P4-T4 | Speed-priority routing picks fastest model | Lowest latency model selected |
| P4-T5 | User overrides model selection for a stage | Override model used, logged as override |
| P4-T6 | Primary model unavailable → fallback used | Fallback model selected, logged |
| P4-T7 | No routing rule for stage type → uses default | Default model used |
| P4-T8 | Routing decision logged with reason | Decision stored in routing_decisions |
| P4-T9 | Model registry returns all available models | Full list with capabilities & pricing |
| P4-T10 | Frontend: Stage editor shows model recommendation | Auto-suggested model displayed |

### ✅ Phase 4 Completion Criteria
- [ ] Router selects different models for different stage types
- [ ] Cost and latency factors influence model selection
- [ ] Fallback works when primary model is unavailable
- [ ] User can override model selection per stage
- [ ] All routing decisions are logged
- [ ] All 10 test cases pass

---

## Phase 5: Advanced Execution — Parallel Stages & Error Handling

### 🎯 Goal
Upgrade the Execution Engine to support **parallel execution of independent stages**, robust **error handling** with retries and fallbacks, and **real-time execution status** via WebSocket. This phase makes the platform production-grade.

### 📋 Requirements

| ID | Requirement | Priority |
|---|---|---|
| P5-R1 | Dependency graph analysis (identify independent/parallel stages) | Must |
| P5-R2 | Parallel execution of independent stages (asyncio) | Must |
| P5-R3 | Merge-point handling (wait for all dependencies before continuing) | Must |
| P5-R4 | Enhanced error handling: retries, exponential backoff | Must |
| P5-R5 | Model fallback on failure (switch to fallback model) | Should |
| P5-R6 | Partial workflow failure handling (fail stage, continue others) | Should |
| P5-R7 | Workflow pause/resume capability | Should |
| P5-R8 | WebSocket for real-time execution status updates | Must |
| P5-R9 | Execution cancellation (stop running workflow) | Should |
| P5-R10 | Stage-level timeout configuration | Should |
| P5-R11 | Frontend: Real-time execution progress (WebSocket) | Must |
| P5-R12 | Frontend: Visual DAG showing execution flow with live status | Should |

### 🏗️ New/Modified Files

```
backend/app/
├── services/
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── dag_analyzer.py        # Dependency graph analysis
│   │   ├── parallel_executor.py   # Async parallel stage execution
│   │   ├── execution_engine.py    # REFACTORED: supports parallel + sequential
│   │   ├── error_handler.py       # Retry, backoff, fallback logic
│   │   └── status_manager.py      # Track & broadcast execution status
│   └── websocket/
│       ├── __init__.py
│       └── execution_ws.py        # WebSocket handler for live status
├── routers/
│   └── websocket.py               # WebSocket endpoints
└── tests/
    ├── test_parallel_execution.py
    ├── test_dag_analyzer.py
    └── test_error_handling.py
```

### 🔄 Execution Flow (Final)

```
Workflow Triggered
    ↓
DAG Analyzer: Build dependency graph
    ↓
Identify stages with no unmet dependencies (ready to run)
    ↓
For each ready stage (in parallel if independent):
    ├── Assemble Stage Input (instruction + relevant context)
    ├── Check Semantic Cache
    │   ├── Cache Hit → Return cached result
    │   └── Cache Miss:
    │       ├── Stage-Aware Router → Select model
    │       ├── Execution Engine → Call LLM
    │       ├── Handle errors (retry/fallback)
    │       ├── Store result in cache
    │       └── Return result
    ├── Update Workflow Context
    ├── Log Execution Metrics
    └── Broadcast status via WebSocket
    ↓
Mark stage complete → Unlock dependent stages
    ↓
Repeat until all stages complete
    ↓
Workflow Complete → Final metrics to Analytics
```

### 🧪 Test Cases

| Test ID | Test Case | Expected Result |
|---|---|---|
| P5-T1 | DAG: 3 sequential stages → runs one at a time | Stages run 1→2→3, no parallelism |
| P5-T2 | DAG: 2 independent stages after stage 1 → run in parallel | Stages 2 & 3 start simultaneously after 1 |
| P5-T3 | Merge: Stage 4 depends on Stages 2 & 3 → waits for both | Stage 4 starts only after 2 and 3 complete |
| P5-T4 | Stage fails → retry 3 times with exponential backoff | 3 retries attempted, then fails |
| P5-T5 | Stage fails → fallback model succeeds | Fallback model used, stage completes |
| P5-T6 | One parallel stage fails, others continue | Failed stage marked, others complete |
| P5-T7 | Pause running workflow → resume later | Workflow pauses at current stage, resumes |
| P5-T8 | Cancel running workflow | All running stages stop, status = cancelled |
| P5-T9 | WebSocket delivers real-time status updates | Frontend receives stage-by-stage updates |
| P5-T10 | Stage timeout (configured 30s) triggers failure | Stage fails after timeout, error logged |
| P5-T11 | Complex DAG: 6 stages with mixed dependencies | Correct parallel/sequential execution |
| P5-T12 | Frontend: DAG visualization shows live stage statuses | Green/yellow/red indicators update in real-time |

### ✅ Phase 5 Completion Criteria
- [ ] Independent stages execute in parallel
- [ ] Merge points correctly wait for all dependencies
- [ ] Retry + fallback error handling works end-to-end
- [ ] WebSocket delivers real-time status to frontend
- [ ] Pause/resume and cancel work for running workflows
- [ ] All 12 test cases pass

---

## Phase 6: Analytics Dashboard & Production Polish

### 🎯 Goal
Build the **Analytics & Dashboard** layer that visualizes execution performance, cache efficiency, cost analysis, and model utilization. Also add final production polish: Docker production configs, comprehensive error pages, and documentation.

### 📋 Requirements

| ID | Requirement | Priority |
|---|---|---|
| P6-R1 | Analytics data aggregation service | Must |
| P6-R2 | Workflow execution summary (total latency, cost, stages) | Must |
| P6-R3 | Stage-level performance metrics (latency, tokens, cost per stage) | Must |
| P6-R4 | Cache performance analytics (hit rate, miss rate, savings) | Must |
| P6-R5 | Model utilization analytics (usage per model, cost per model) | Must |
| P6-R6 | Token usage analytics (input/output tokens, trends) | Must |
| P6-R7 | Cost analytics (estimated cost per workflow, per stage, per model) | Must |
| P6-R8 | Time-series analytics (performance over time) | Should |
| P6-R9 | Analytics API endpoints | Must |
| P6-R10 | Dashboard: Overview page with key metrics | Must |
| P6-R11 | Dashboard: Workflow execution timeline/Gantt chart | Should |
| P6-R12 | Dashboard: Cache performance charts (hit/miss pie, savings bar) | Must |
| P6-R13 | Dashboard: Model usage breakdown (bar/pie charts) | Must |
| P6-R14 | Dashboard: Cost summary with trends | Must |
| P6-R15 | Dashboard: Latency breakdown per stage | Should |
| P6-R16 | Dashboard: Export analytics data (CSV/JSON) | Should |
| P6-R17 | Production Docker Compose with Nginx reverse proxy | Should |
| P6-R18 | Comprehensive API documentation | Must |
| P6-R19 | User guide / README documentation | Must |

### 🏗️ New/Modified Files

```
backend/app/
├── services/
│   └── analytics/
│       ├── __init__.py
│       ├── aggregator.py          # Data aggregation & computation
│       ├── metrics.py             # Metric definitions & calculations
│       └── export.py              # CSV/JSON export
├── schemas/
│   └── analytics.py              # Analytics response schemas
├── routers/
│   └── analytics.py              # Analytics API endpoints
└── tests/
    └── test_analytics.py

frontend/src/
├── pages/
│   └── Dashboard.tsx              # Main analytics dashboard
├── components/
│   ├── charts/
│   │   ├── LatencyChart.tsx       # Stage latency visualization
│   │   ├── CacheChart.tsx         # Cache hit/miss visualization
│   │   ├── CostChart.tsx          # Cost breakdown charts
│   │   ├── ModelUsageChart.tsx    # Model utilization charts
│   │   ├── TokenChart.tsx         # Token usage visualization
│   │   └── TimelineChart.tsx      # Execution timeline/Gantt
│   ├── metrics/
│   │   ├── MetricCard.tsx         # Single metric display card
│   │   └── MetricGrid.tsx         # Grid of metric cards
│   └── analytics/
│       ├── WorkflowSummary.tsx    # Workflow execution summary
│       └── ExportButton.tsx       # Data export component
```

### 📊 Analytics API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/analytics/overview` | GET | Key metrics: total workflows, executions, avg latency, total cost |
| `/analytics/workflows/{id}` | GET | Per-workflow execution summary |
| `/analytics/cache` | GET | Cache hit rate, miss rate, cost savings, entries count |
| `/analytics/models` | GET | Model utilization, cost per model, calls per model |
| `/analytics/tokens` | GET | Token usage (input/output), trends over time |
| `/analytics/costs` | GET | Cost breakdown by workflow, stage, model, time period |
| `/analytics/latency` | GET | Latency percentiles, per-stage breakdown |
| `/analytics/timeline/{execution_id}` | GET | Execution timeline for Gantt chart |
| `/analytics/export` | GET | Export all data as CSV/JSON |

### 🧪 Test Cases

| Test ID | Test Case | Expected Result |
|---|---|---|
| P6-T1 | GET /analytics/overview returns valid metrics | All key metrics present and correct |
| P6-T2 | Cache analytics: 5 hits + 3 misses → 62.5% hit rate | Correct percentage calculated |
| P6-T3 | Cost analytics after 10 executions | Total cost matches sum of execution costs |
| P6-T4 | Model usage: 3 models used → breakdown correct | Each model's call count and cost accurate |
| P6-T5 | Token analytics: total input + output tokens | Sum matches individual execution records |
| P6-T6 | Latency analytics: avg, p50, p95, p99 | Percentiles calculated correctly |
| P6-T7 | Export analytics as CSV | Valid CSV file with all data |
| P6-T8 | Export analytics as JSON | Valid JSON matching API schema |
| P6-T9 | Dashboard: Overview page loads with charts | All charts render with data |
| P6-T10 | Dashboard: Filter analytics by date range | Data filtered correctly |
| P6-T11 | Dashboard: Execution timeline shows parallel stages | Gantt chart shows overlapping bars |
| P6-T12 | Empty state: No executions yet → dashboard shows zeros | No errors, graceful empty state |

### ✅ Phase 6 Completion Criteria
- [ ] Analytics API returns accurate aggregated metrics
- [ ] Dashboard displays all charts: latency, cache, cost, model usage, tokens
- [ ] Execution timeline/Gantt chart shows parallel stages
- [ ] Data export works in CSV and JSON
- [ ] Production Docker setup works
- [ ] Complete API documentation available
- [ ] All 12 test cases pass

---

## Summary — Phase Overview

| Phase | Focus Area | Key Deliverable | Est. Complexity |
|---|---|---|---|
| **Phase 1** | Foundation & Workflow Manager | Workflow/Stage CRUD + UI + DB | ⭐⭐ Medium |
| **Phase 2** | Context Management & LLM Integration | Working sequential execution | ⭐⭐⭐ High |
| **Phase 3** | Semantic Caching & Embeddings | Cache-hit optimization | ⭐⭐⭐ High |
| **Phase 4** | Stage-Aware Routing | Intelligent model selection | ⭐⭐ Medium |
| **Phase 5** | Parallel Execution & Error Handling | Production-grade execution engine | ⭐⭐⭐ High |
| **Phase 6** | Analytics Dashboard & Polish | Full analytics + production ready | ⭐⭐ Medium |

### Total Requirements: **74** | Total Test Cases: **74**

---

## Complete Execution Flow (All Phases Combined)

```
User → Workflow Manager (Phase 1)
  → Define Workflow + Stages + Dependencies
  → Trigger Execution
    ↓
DAG Analyzer (Phase 5) → Determine execution order + parallelism
    ↓
For each ready stage:
  → Context Manager (Phase 2) → Assemble relevant input
  → Semantic Cache (Phase 3) → Check for cached result
    ├── Cache Hit → Return cached result
    └── Cache Miss:
        → Stage-Aware Router (Phase 4) → Select best model
        → Execution Engine (Phase 2+5) → Call LLM (with retry/fallback)
        → Store result in cache
  → Update Workflow Context
  → Log Execution Metrics → Analytics (Phase 6)
  → Broadcast status via WebSocket (Phase 5)
    ↓
All stages complete → Dashboard (Phase 6) → Visualize performance
```

> [!TIP]
> **Recommended approach**: Complete and test each phase fully before moving to the next. Each phase produces a working, demonstrable increment of the platform.

> [!NOTE]
> **Future Enhancements** (beyond these 6 phases): Automatic Workflow Planner (AI generates stages from objectives), DAG-based auto-scheduling, budget-aware optimization, adaptive routing from historical data, and learning-based cache invalidation. These are documented in the PDF but intentionally deferred.
