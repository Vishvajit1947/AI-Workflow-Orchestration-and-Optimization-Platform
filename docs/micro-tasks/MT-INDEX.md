# Micro-Task Index — AI Workflow Orchestration Platform

> Execute micro-tasks **in order**. Each MT lists its prerequisites. Do not skip ahead.

## Phase 0 — Repo Scaffold

| MT | Title | Prerequisites | Delivers |
|----|-------|---------------|----------|
| [MT-00](MT-00.md) | Repo Scaffold, `.gitignore`, README Stub | None | Folder tree, git init, docker-compose skeleton |

---

## Phase 1 — Foundation & Workflow Manager (CRUD)

| MT | Title | Prerequisites | Delivers |
|----|-------|---------------|----------|
| [MT-01](MT-01.md) | Backend FastAPI App Setup | MT-00 | `main.py`, `config.py`, `database.py`, `requirements.txt`, `Dockerfile` |
| [MT-02](MT-02.md) | Database ORM Models | MT-01 | `workflow.py`, `stage.py` (SQLAlchemy models) |
| [MT-03](MT-03.md) | Alembic Setup & Initial Migration | MT-02 | `alembic.ini`, `env.py`, first migration |
| [MT-04](MT-04.md) | Pydantic Schemas | MT-02 | Request/response schemas for workflows & stages |
| [MT-05](MT-05.md) | Workflow CRUD Service & API | MT-03, MT-04 | `/api/workflows` endpoints + service layer |
| [MT-06](MT-06.md) | Stage CRUD Service & API | MT-05 | `/api/stages` endpoints + service layer |
| [MT-07](MT-07.md) | Dependency Management & Validation | MT-06 | Cycle detection, workflow validation |
| [MT-08](MT-08.md) | Frontend Scaffold | MT-00 | Vite + React + TS + Tailwind + Router |
| [MT-09](MT-09.md) | Frontend Workflow Pages | MT-05, MT-08 | Workflow list, create, edit, detail pages |
| [MT-10](MT-10.md) | Frontend Stage Editor & Phase 1 Tests | MT-06, MT-07, MT-09 | Stage editor UI + all Phase 1 pytest/vitest |

---

## Phase 2 — Context Management & LLM Integration

| MT | Title | Prerequisites | Delivers |
|----|-------|---------------|----------|
| [MT-11](MT-11.md) | Context Model & Manager Service | MT-03 | `workflow_context` table, context CRUD service |
| [MT-12](MT-12.md) | LLM Provider Abstraction & OpenAI | MT-01 | Base provider interface, OpenAI implementation |
| [MT-13](MT-13.md) | Anthropic & Gemini Providers | MT-12 | Claude + Gemini provider implementations |
| [MT-14](MT-14.md) | Sequential Execution Engine | MT-11, MT-12 | Run stages in order, store results |
| [MT-15](MT-15.md) | Execution API & Status Tracking | MT-14 | `/api/executions` endpoints, status model |
| [MT-16](MT-16.md) | Frontend Execution UI | MT-09, MT-15 | Execute button, progress, results display |
| [MT-17](MT-17.md) | Phase 2 Integration Tests | MT-16 | Full context + execution test suite |

---

## Phase 3 — Semantic Caching & Embeddings

| MT | Title | Prerequisites | Delivers |
|----|-------|---------------|----------|
| [MT-18](MT-18.md) | Embedding Service & pgvector Setup | MT-03 | Embedding generation, pgvector extension + migration |
| [MT-19](MT-19.md) | Semantic Cache Model & Service | MT-18 | `cache_entries` table, cache lookup/store |
| [MT-20](MT-20.md) | Workflow-Aware Cache Validation | MT-19 | Dependency-hash invalidation, TTL expiry |
| [MT-21](MT-21.md) | Cache Integration & Management API | MT-14, MT-20 | Cache check in execution flow, `/api/cache` endpoints |
| [MT-22](MT-22.md) | Frontend Cache UI | MT-16, MT-21 | Cache indicators, cache management page |
| [MT-23](MT-23.md) | Phase 3 Integration Tests | MT-22 | Full caching test suite |

---

## Phase 4 — Stage-Aware Routing ✅

| MT | Title | Prerequisites | Delivers |
|----|-------|---------------|----------|
| [MT-24](MT-24.md) | Model Registry & Capability Profiles | MT-03 | `model_profiles` table, registry service |
| [MT-25](MT-25.md) | Routing Engine & Rules | MT-24 | Stage-to-model matching, cost/latency routing |
| [MT-26](MT-26.md) | Router Integration into Execution | MT-21, MT-25 | Router in execution flow, routing decisions log |
| [MT-27](MT-27.md) | Frontend Routing Config UI | MT-16, MT-26 | Model selection, routing rules page |
| [MT-28](MT-28.md) | Phase 4 Integration Tests | MT-27 | Full routing test suite |

---

## Phase 5 — Parallel Execution & Error Handling ✅

| MT | Title | Prerequisites | Delivers |
|----|-------|---------------|----------|
| [MT-29](MT-29.md) | DAG Analyzer | MT-07 | Dependency graph builder, topological sort |
| [MT-30](MT-30.md) | Parallel Executor | MT-14, MT-29 | Async parallel stage execution |
| [MT-31](MT-31.md) | Enhanced Error Handling | MT-30 | Retry, exponential backoff, model fallback |
| [MT-32](MT-32.md) | WebSocket Real-Time Status | MT-30 | WebSocket endpoint, status broadcasts |
| [MT-33](MT-33.md) | Workflow Pause, Resume & Cancel | MT-30 | Pause/resume/cancel API + state machine |
| [MT-34](MT-34.md) | Frontend Real-Time UI & DAG Visualization | MT-16, MT-32 | Live DAG, WebSocket status, controls |
| [MT-35](MT-35.md) | Phase 5 Integration Tests | MT-34 | Full parallel execution test suite |

---

## Phase 6 — Analytics Dashboard & Production Polish ✅

| MT | Title | Prerequisites | Delivers |
|----|-------|---------------|----------|
| [MT-36](MT-36.md) | Analytics Aggregation Service | MT-15 | Metrics computation, aggregation queries |
| [MT-37](MT-37.md) | Analytics API Endpoints | MT-36 | `/api/analytics/*` endpoints |
| [MT-38](MT-38.md) | Frontend Dashboard Overview & Metric Cards | MT-08, MT-37 | Dashboard page, KPI cards |
| [MT-39](MT-39.md) | Frontend Charts (Latency, Cache, Cost, Model) | MT-38 | Recharts visualizations |
| [MT-40](MT-40.md) | Execution Timeline, Export & Final Polish | MT-39 | Gantt chart, CSV/JSON export, final README |

---

## Summary

| Phase | MTs | Count |
|-------|-----|-------|
| Phase 0 | MT-00 | 1 |
| Phase 1 | MT-01 — MT-10 | 10 |
| Phase 2 | MT-11 — MT-17 | 7 |
| Phase 3 | MT-18 — MT-23 | 6 |
| Phase 4 | MT-24 — MT-28 | 5 |
| Phase 5 | MT-29 — MT-35 | 7 |
| Phase 6 | MT-36 — MT-40 | 5 |
| **Total** | **MT-00 — MT-40** | **41** |
