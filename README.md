# AI Workflow Orchestration and Optimization Platform

A full-stack platform for running multi-stage AI workflows across several LLM providers. Instead of
sending every request to one model, it runs a workflow as a graph of stages and:

- **passes context** between stages (each stage sees only the outputs it depends on),
- **reuses results** through a semantic cache (pgvector similarity search, invalidated when upstream outputs change),
- **routes each stage** to the model that best fits its type, cost and latency limits,
- **runs independent stages in parallel**, with retries, timeouts, circuit breakers and model fallback,
- **reports** cost, tokens, latency, cache savings and routing on an analytics dashboard.

## Project status

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Repo scaffold | ✅ |
| 1 | Workflow & stage management (CRUD, dependencies, validation) | ✅ |
| 2 | Context management & LLM providers (OpenAI, Anthropic, Gemini, Groq) | ✅ |
| 3 | Semantic caching with pgvector | ✅ |
| 4 | Stage-aware model routing | ✅ |
| 5 | Parallel DAG execution, error handling, live status, pause/resume/cancel | ✅ |
| 6 | Analytics dashboard, execution timeline, export, production deployment | ✅ |

## Features

**Workflows** — stages with an instruction, type (analysis, design, generation, testing,
documentation, review, custom) and optional model preference. Stages sharing a `stage_order`
run in parallel; explicit stage dependencies override the order. Cycles are rejected.

**Execution** — a DAG scheduler starts each stage as soon as its dependencies complete (up to
`MAX_PARALLEL_STAGES` at once). A failed stage skips only its descendants. Executions can run in the
background with live per-stage status over a WebSocket, and can be paused, resumed or cancelled.

**Semantic cache** — each stage input is embedded and compared with earlier inputs of the same stage
type; above `CACHE_SIMILARITY_THRESHOLD` the stored result is reused at zero cost. Entries carry a
hash of their upstream outputs, so a changed dependency never serves a stale result.

**Routing** — a model registry (capability scores per stage type, pricing, latency) and per-type
routing rules (priority: cost / speed / quality / balanced; limits on cost, latency and minimum score;
preferred and fallback models). Only models whose provider has an API key are chosen. Every decision
is logged with its reason. Per-execution overrides are supported.

**Resilience** — errors are classified (transient / rate limit / permanent) by status code and
exception type; transient errors retry with exponential backoff, each attempt has a timeout, a
per-provider circuit breaker stops calling a failing provider, and a failed model falls back to the
routing rule's fallback model.

**Analytics** — dashboard with success rate, cost, tokens, LLM latency percentiles (real
`percentile_cont`, not estimates), cache hit rate and savings, model usage, routing overrides and
fallbacks, and per-stage-type breakdowns; filterable by date range and workflow. Per-execution
Gantt timeline. CSV/JSON export of the summary or of every stage run.

## Architecture

```text
 Browser ── React SPA (Vite, Tailwind)
   │  REST /api/*          WebSocket /ws/executions/{id}
   ▼
 nginx (production) ──► FastAPI backend (single process)
                          ├─ workflow / stage services
                          ├─ execution engine ── DAG analyzer, scheduler, error handler
                          │     ├─ context manager (dependency outputs → stage input)
                          │     ├─ semantic cache (embeddings + pgvector)
                          │     ├─ routing engine (registry + rules)
                          │     └─ LLM providers: OpenAI · Anthropic · Gemini · Groq
                          ├─ live tracker (status, pause/resume/cancel) → WebSocket
                          └─ analytics aggregator / exporter
                               │
                               ▼
                     PostgreSQL 15 + pgvector
```

Live execution state (running stages, pause/cancel flags, WebSocket subscribers) is held in the
backend process, so the backend runs as **one** process. On startup, any workflow left `running` or
`paused` by a previous process is marked `failed`.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2 (async) · Alembic · Pydantic 2 |
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS (charts are hand-built SVG) |
| Database | PostgreSQL 15 · pgvector |
| LLMs | OpenAI · Anthropic · Google Gemini · Groq |
| Embeddings | OpenAI `text-embedding-3-small`, or local sentence-transformers |
| Deployment | Docker Compose · nginx |
| Testing | pytest · pytest-asyncio · Vitest · React Testing Library |

## Quick start (Docker, production stack)

```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD and GOOGLE_API_KEY and/or GROQ_API_KEY
docker compose -f docker-compose.prod.yml up -d --build
```

> **Providers:** the deployed configuration uses **Gemini** and **Groq**; the workflow planner prefers Groq.
> OpenAI and Anthropic adapters remain in the codebase but are registered only if their keys are set.

Open <http://localhost> (or `HTTP_PORT`). The API docs are at <http://localhost/docs>.
Migrations run automatically when the backend container starts; the model registry and default
routing rules are seeded on first start. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for HTTPS,
backups and operations.

## Local development

Prerequisites: Python 3.11+, Node 18+, PostgreSQL 15 with the pgvector extension
(e.g. the `pgvector/pgvector:pg15` image).

```bash
# Backend (run from the repo root: imports are `backend.app...`)
pip install -r backend/requirements.txt
cp .env.example .env                      # set DATABASE_URL / DATABASE_URL_SYNC and API keys
cd backend && alembic upgrade head && cd ..
uvicorn backend.app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev                               # http://localhost:5173, API at http://localhost:8000
```

Set `VITE_API_BASE_URL` to point the frontend at another backend; an empty value means "same origin"
(used behind nginx).

### Database migrations

```bash
cd backend
alembic upgrade head                      # apply all
alembic revision -m "describe change"     # new migration (edit the generated file)
alembic downgrade -1                      # roll back one
```

## Configuration

All settings are environment variables (or `.env`), defined in `backend/app/config.py`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | local Postgres (asyncpg) | Application database |
| `DATABASE_URL_SYNC` | local Postgres (psycopg2) | Used by Alembic |
| `CORS_ORIGINS` | localhost dev origins | JSON list of allowed browser origins |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY` | — | A provider is available only when its key is set |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `local` (sentence-transformers) |
| `CACHE_SIMILARITY_THRESHOLD` | `0.92` | Cosine similarity needed for a cache hit |
| `CACHE_TTL_SECONDS` | `86400` | Cache entry lifetime |
| `CACHE_ENABLE_WORKFLOW_VALIDATION` | `true` | Invalidate entries when upstream outputs change |
| `MAX_PARALLEL_STAGES` | `4` | Concurrent stages per execution |
| `MAX_RETRIES` | `3` | Attempts per model before falling back |
| `RETRY_BACKOFF_INITIAL_SECONDS`, `RETRY_BACKOFF_BASE` | `1.0`, `2` | Backoff: initial × base^(attempt−1) |
| `RATE_LIMIT_BACKOFF_SECONDS` | `30` | Wait after a rate-limit error |
| `STAGE_TIMEOUT_SECONDS` | `120` | Timeout per LLM attempt |
| `CIRCUIT_BREAKER_THRESHOLD`, `CIRCUIT_BREAKER_TIMEOUT` | `5`, `60` | Failures that open a provider's circuit; seconds until a trial call |

## API overview

Interactive documentation: `/docs` (Swagger UI) and `/redoc`.

| Area | Endpoints |
|------|-----------|
| Workflows & stages | `/api/workflows`, `/api/stages`, `/api/workflows/{id}/validate`, `/api/workflows/{id}/dag` |
| Execution | `POST /api/workflows/{id}/execute` (`parallel`, `background`, `use_cache`, `use_routing`, `routing_preferences`), `/api/executions`, `/api/executions/{id}`, `/api/executions/{id}/status`, `/api/executions/{id}/pause\|resume\|cancel` |
| Live status | `WS /ws/executions/{id}` — snapshot on connect, then `stage_update` / `execution_status`; send `ping` for `pong` |
| Cache | `/api/cache/stats`, `/api/cache/entries`, `/api/cache/clear`, `/api/cache/cleanup-expired` |
| Models & routing | `/api/models`, `/api/models/compare`, `/api/routing/rules`, `/api/routing/decisions`, `/api/routing/preview/{workflow_id}` |
| Analytics | `/api/analytics/overview`, `/cache`, `/models`, `/latency`, `/costs`, `/tokens`, `/routing`, `/stage-types`, `/timeline/{execution_id}`, `/export?format=csv\|json&dataset=summary\|stage_runs` |
| Health | `GET /health` |

Analytics endpoints accept `start_date`, `end_date` (ISO 8601; naive values are UTC) and `workflow_id`.

## Testing

```bash
# Backend (from the repo root) — integration tests use a separate database, ai_orchestrator_test
# (set TEST_DATABASE_URL to override; tables are created and dropped per test)
python -m pytest backend/tests -c backend/pytest.ini --rootdir backend               # everything
python -m pytest backend/tests/unit -c backend/pytest.ini --rootdir backend          # no database needed
python -m pytest backend/tests/integration -c backend/pytest.ini --rootdir backend   # needs Postgres + pgvector
python -m pytest backend/tests/e2e -c backend/pytest.ini --rootdir backend           # real Groq API

# Frontend
cd frontend && npm test
```

| Directory | Contents |
|-----------|----------|
| `backend/tests/unit/` | Isolated logic: DAG analyzer, error handler, LLM provider adapters (SDKs mocked), embedding service |
| `backend/tests/integration/` | Services and API endpoints against the test database: workflows, stages, planner, execution, context, cache, routing, analytics, WebSocket |
| `backend/tests/e2e/` | Live planner test against the real Groq API; skipped unless `GROQ_API_KEY` is set |

Unit and integration tests send LLM calls to stub providers, so no API keys are needed.

## Measured behaviour

From the automated tests (stub LLMs with fixed delays, local Postgres):

- Four independent stages with 0.5 s LLM latency: **~1.2 s in parallel vs ~2.65 s sequential (≈2.1×)**;
  the remainder is per-stage database work, which is serialized.
- A stage served from the semantic cache makes no LLM call: zero tokens and cost, and near-zero latency.
- A routed workflow (analysis, generation, testing, documentation) cost **under half** of sending every
  stage to the premium model, while the generation stage still got the top generation model.

Real-world savings depend on your workload (how often inputs repeat, which models you allow).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `extension "vector" is not available` during migrations | Use a Postgres image with pgvector (`pgvector/pgvector:pg15`) |
| Executions fail with `Provider 'openai' not registered` | Set at least one provider API key; routing only picks providers with keys |
| Every stage shows "fallback" in results | No registered model is routable — check API keys and that models are enabled on **Models & Routing** |
| Cache never hits | Check `EMBEDDING_PROVIDER` works (OpenAI key or local model); the cache is skipped when embeddings fail |
| "Workflow is already running" after a crash | Restart the backend: interrupted workflows are marked failed on startup |
| Live status says "polling" | The WebSocket could not connect; behind a proxy make sure `/ws/` is forwarded with `Upgrade` headers |

## Directory structure

```text
backend/
  app/
    api/            REST + WebSocket routes
    models/         SQLAlchemy models
    schemas/        Pydantic schemas
    services/       execution (DAG, scheduler, errors, tracker), cache, router, llm, analytics, websocket
  alembic/          migrations
  scripts/          developer tools (DAG visualizer, provider model listing, Windows backend launcher)
  tests/            pytest suite: unit/, integration/, e2e/ (shared fixtures in conftest.py)
frontend/
  src/
    pages/          Dashboard, Workflows, Executions, Cache, Models & Routing
    components/     charts, DAG view, execution monitor, editors
    api/ lib/ types/ hooks/
  tests/            Vitest suite
nginx/              reverse proxy config (production)
docs/               specs, micro-task plans, deployment guide
explanations/       design notes for the early micro-tasks
docker-compose.yml       development stack (Postgres, Redis, backend, frontend)
docker-compose.prod.yml  production stack (Postgres, backend, nginx + built frontend)
```

### Developer scripts

```bash
python -m backend.scripts.visualize_dag <workflow_id>   # print a workflow's DAG levels and critical path
python backend/scripts/check_gemini_models.py           # list Gemini models available to GOOGLE_API_KEY
python backend/scripts/list_groq_models.py              # list Groq models available to GROQ_API_KEY
./backend/scripts/start_backend.ps1                     # Windows: run migrations, then start the API
```
