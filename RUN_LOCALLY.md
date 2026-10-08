# AI Workflow Orchestration Platform - Local Setup Guide

Windows (PowerShell) walkthrough. For Docker and the full configuration reference, see [README.md](README.md).

- Backend API: http://localhost:8000
- Database: PostgreSQL with the pgvector extension
- Configured LLM providers: **Gemini** and **Groq**

## Prerequisites

- Python 3.11
- PostgreSQL 15+ with the pgvector extension (e.g. the `pgvector/pgvector:pg15` Docker image)
- Node 18+ (frontend)
- Git

## Quick Start

### 1. Backend Setup

All commands start from the repository root.

```powershell
# Create and activate the virtual environment
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies (if not already done)
pip install -r requirements.txt

# Run database migrations
python -m alembic upgrade head

# Start the backend server
cd ..
.\backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

The backend will be available at: http://localhost:8000

Alternatively, `.\backend\scripts\start_backend.ps1` runs the migrations and starts the server in one step.

### 2. Verify Backend is Running

```powershell
# Check health endpoint
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing

# Check available models (should show only Gemini and Groq)
Invoke-WebRequest -Uri "http://localhost:8000/api/models" -UseBasicParsing
```

### 3. Frontend Setup

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173
```

## Environment Configuration

Copy `.env.example` to `.env` in the repository root and set at least:

```env
# Database
DATABASE_URL=postgresql+asyncpg://orchestrator:orchestrator_dev@localhost:5433/ai_orchestrator

# LLM Providers (production configuration)
GOOGLE_API_KEY=<your-gemini-key>
GROQ_API_KEY=<your-groq-key>

# Not used in the production configuration (leave empty)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Embedding
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## API Endpoints

### Planner
- `POST /api/planner/analyze` - Turn an objective into a proposed plan (simple or multi-stage DAG)
- `POST /api/planner/generate` - Create a workflow from an approved plan

### Workflows
- `POST /api/workflows` - Create workflow
- `GET /api/workflows` - List workflows
- `POST /api/workflows/{id}/execute` - Execute workflow
- `GET /api/workflows/{id}` - Get workflow details

### Stages
- `POST /api/stages` - Create stage
- `GET /api/stages/workflow/{workflow_id}` - List a workflow's stages
- `PATCH /api/stages/{id}` - Update stage
- `POST /api/stages/{id}/dependencies` - Add a dependency

### Executions
- `GET /api/executions/{id}` - Get execution details
- `GET /api/executions` - List executions

### Models
- `GET /api/models` - List available models (Gemini & Groq only)
- `GET /api/models/compare` - Compare models

### Cache
- `GET /api/cache/stats` - Cache statistics
- `GET /api/cache/entries` - List cache entries
- `POST /api/cache/clear` - Clear cache
- `POST /api/cache/cleanup-expired` - Remove expired entries

### Analytics
- `GET /api/analytics/overview` - Summary metrics
- `GET /api/analytics/costs` - Cost analytics
- `GET /api/analytics/export?format=csv|json` - Export

## Example: Create and Execute a Simple Workflow

```powershell
# 1. Create a workflow
$workflow = Invoke-RestMethod -Uri "http://localhost:8000/api/workflows" -Method Post -ContentType "application/json" -Body '{"name":"Test Workflow","objective":"Test the system"}'

# 2. Create a stage
$stage = Invoke-RestMethod -Uri "http://localhost:8000/api/stages" -Method Post -ContentType "application/json" -Body "{`"workflow_id`":`"$($workflow.id)`",`"name`":`"Analysis`",`"instruction`":`"Analyze requirements`",`"stage_order`":0,`"stage_type`":`"analysis`"}"

# 3. Execute the workflow
$execution = Invoke-RestMethod -Uri "http://localhost:8000/api/workflows/$($workflow.id)/execute" -Method Post -ContentType "application/json" -Body '{"default_provider":"gemini"}'

# 4. Get execution results
Start-Sleep -Seconds 5
$result = Invoke-RestMethod -Uri "http://localhost:8000/api/executions/$($execution.execution_id)"
$result | ConvertTo-Json -Depth 10
```

## Running Tests

From the repository root. Integration tests need Postgres with pgvector and a database named
`ai_orchestrator_test` (override with `TEST_DATABASE_URL`).

```powershell
# Unit tests (no database)
.\backend\venv\Scripts\python.exe -m pytest backend\tests\unit -c backend\pytest.ini --rootdir backend

# Integration tests
.\backend\venv\Scripts\python.exe -m pytest backend\tests\integration -c backend\pytest.ini --rootdir backend

# End-to-end planner test against the real Groq API (skipped without GROQ_API_KEY)
.\backend\venv\Scripts\python.exe -m pytest backend\tests\e2e -c backend\pytest.ini --rootdir backend
```

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│              User Request                    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│          Workflow Manager                    │
│  • Create workflows & stages                 │
│  • Manage dependencies (DAG)                 │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│         Execution Engine                     │
│  • Parallel/Sequential execution             │
│  • DAG analyzer & scheduler                  │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│        Context Manager                       │
│  • Stage context & history                   │
│  • Cross-stage data flow                     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│        Semantic Cache                        │
│  • pgvector similarity search                │
│  • Dependency-aware invalidation             │
│  • Token & cost savings                      │
└──────────────────┬──────────────────────────┘
                   │
            ┌──────┴──────┐
            │   Cache?    │
            └──────┬──────┘
         Hit │     │ Miss
             │     │
             │     ▼
             │  ┌─────────────────────────────┐
             │  │    Routing Engine            │
             │  │  • Model selection           │
             │  │  • Provider routing          │
             │  └──────────┬──────────────────┘
             │             │
             │             ▼
             │  ┌─────────────────────────────┐
             │  │    LLM Providers             │
             │  │  • Gemini (Google)           │
             │  │  • Groq (Qwen, GPT-OSS)      │
             │  └──────────┬──────────────────┘
             │             │
             └─────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│          Analytics & Monitoring              │
│  • Cost tracking                             │
│  • Performance metrics                       │
│  • WebSocket live updates                    │
└─────────────────────────────────────────────┘
```

## Key Features

### 1. Semantic Caching
- Uses pgvector for similarity-based cache lookups
- Automatically invalidates downstream stages when dependencies change
- Tracks token savings and cost reduction

### 2. Intelligent Routing
- Selects optimal models based on:
  - Stage type (analysis, design, generation, etc.)
  - Cost constraints
  - Latency requirements
  - Capability scores
- Only routes to Gemini and Groq (no OpenAI/Anthropic)

### 3. DAG Execution
- Analyzes workflow dependencies
- Executes independent stages in parallel
- Maintains proper execution order
- Handles errors and retries

### 4. Provider Architecture
- Provider-agnostic design
- Only registered providers are available
- Graceful fallback handling
- Circuit breaker pattern for failures

## Troubleshooting

### Backend won't start
```powershell
# Check PostgreSQL is running
Get-Process postgres

# Check port 8000 is available
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

The backend logs to the console it was started from.

### Database connection errors
```powershell
# Test database connection
psql -h localhost -p 5433 -U orchestrator -d ai_orchestrator

# Run migrations
cd backend
.\venv\Scripts\python.exe -m alembic upgrade head
```

### Model execution failures
- Verify API keys are set in `.env`
- Check model availability: GET /api/models
- Review execution logs for error details

## Production Deployment

For production deployment:

1. Use production database credentials
2. Set `ENVIRONMENT=production` in `.env`
3. Use a process manager (PM2, systemd, Docker)
4. Set up reverse proxy (nginx, Caddy)
5. Enable HTTPS
6. Configure CORS properly
7. Set up monitoring and logging

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the Docker-based production stack.

## Support

For issues or questions:
1. Check the backend console output
2. Run diagnostics: `python -m pytest backend/tests/integration/test_phase2_integration.py -c backend/pytest.ini --rootdir backend`
3. Verify configuration: Check `.env` file
4. Review API docs: http://localhost:8000/docs (Swagger UI)
