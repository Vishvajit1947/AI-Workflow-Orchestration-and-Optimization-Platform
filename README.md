# AI Workflow Orchestration and Optimization Platform

A full-stack platform that manages and optimizes multi-stage AI workflows using multiple Large
Language Models (LLMs). Instead of sending every request directly to a single LLM, the platform
orchestrates a workflow of multiple stages — maintaining context between stages, reusing
semantically similar results, selecting the best LLM for each stage, and analyzing performance.

> **This is a stub README.** The full quickstart guide, architecture diagrams, screenshots, and
> deployment instructions will be added in a later micro-task. For now, see the project
> specification in [`PBL Project Planning for Sem-5.pdf`](PBL%20Project%20Planning%20for%20Sem-5.pdf).

## Project Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Repo scaffold (MT-00) | ✅ Complete |
| Phase 1 | Workflow Manager (CRUD) | 🔲 Not started |
| Phase 2 | Context Management & LLM Integration | 🔲 Not started |
| Phase 3 | Semantic Caching & Embeddings | 🔲 Not started |
| Phase 4 | Stage-Aware Routing | 🔲 Not started |
| Phase 5 | Parallel Execution & Error Handling | 🔲 Not started |
| Phase 6 | Analytics Dashboard & Polish | 🔲 Not started |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11 · FastAPI · Uvicorn · SQLAlchemy · Alembic |
| **Frontend** | React 18 · TypeScript · Vite · Tailwind CSS |
| **Database** | PostgreSQL 15 · pgvector (for semantic search) |
| **Caching** | Redis 7 |
| **LLM Providers** | OpenAI · Anthropic (Claude) · Google Gemini |
| **DevOps** | Docker Compose · Git/GitHub |
| **Testing** | pytest · React Testing Library · Vitest |

## Directory Structure

```text
.
├── backend/                    # FastAPI backend
│   ├── app/                    # Main application package
│   │   ├── api/                # API route handlers
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic layer
│   │   │   ├── llm/            # LLM provider abstraction
│   │   │   ├── cache/          # Semantic caching engine
│   │   │   ├── router/         # Stage-aware model routing
│   │   │   ├── execution/      # Workflow execution engine
│   │   │   ├── analytics/      # Metrics aggregation
│   │   │   └── websocket/      # Real-time status updates
│   │   ├── ml/                 # Pre-trained model artifacts
│   │   └── utils/              # Shared utilities
│   ├── alembic/                # Database migrations
│   └── tests/                  # Backend test suite
├── frontend/                   # React + Vite frontend
│   ├── src/
│   │   ├── api/                # API client
│   │   ├── pages/              # Page components
│   │   ├── components/         # Reusable UI components
│   │   └── types/              # TypeScript type definitions
│   └── public/                 # Static assets
├── docs/                       # Project documentation
├── docker-compose.yml          # Multi-service orchestration
├── .env.example                # Environment variable template
└── README.md                   # This file
```

## Quick Start

> Coming soon — will be added after backend and frontend are implemented.
