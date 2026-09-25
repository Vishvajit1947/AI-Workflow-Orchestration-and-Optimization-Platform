# MT-00 Explanation: Repository Scaffold Setup

## 📚 Table of Contents
1. [Overview](#overview)
2. [What We're Building](#what-were-building)
3. [Why This Task Matters](#why-this-task-matters)
4. [Directory Structure Explained](#directory-structure-explained)
5. [Configuration Files Explained](#configuration-files-explained)
6. [Git Setup Explained](#git-setup-explained)
7. [Step-by-Step Execution](#step-by-step-execution)

---

## Overview

**MT-00** is the very first micro-task in building our AI Workflow Orchestration Platform. Think of it as laying the foundation before building a house. We're creating the complete folder structure, essential configuration files, and initializing version control.

### What Gets Created?
- **23 directories** for backend, frontend, and documentation
- **15 `__init__.py` files** to make Python packages work
- **10 `.gitkeep` files** to preserve empty directories in git
- **4 configuration files**: `.gitignore`, `README.md`, `docker-compose.yml`, `.env.example`
- **Git repository initialization** with the first commit

---

## What We're Building

This project is a **full-stack AI workflow orchestration platform**. Instead of sending a request to a single AI model, this platform:

1. Breaks down complex tasks into multiple stages
2. Routes each stage to the best AI model for that job
3. Maintains context between stages
4. Caches similar results to save time and money
5. Provides analytics on performance

### Tech Stack Overview

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | Python + FastAPI | API server, business logic |
| **Frontend** | React + TypeScript | User interface |
| **Database** | PostgreSQL 15 | Store workflows, stages, results |
| **Cache** | Redis 7 | Fast caching and vector search |
| **Container** | Docker Compose | Run all services together |
| **AI Models** | OpenAI, Claude, Gemini | Different LLMs for different tasks |

---

## Why This Task Matters

### 1. **Clean Organization from Day 1**
Setting up the complete folder structure now means:
- Every developer knows where to put new files
- No confusion about project organization
- Easier to find and maintain code

### 2. **Professional Development Practices**
- `.gitignore` prevents committing junk files (like `__pycache__/`, `node_modules/`)
- `.env.example` documents all configuration needs
- `README.md` provides project overview
- Docker Compose enables consistent development environments

### 3. **Python Package Structure**
Python needs `__init__.py` files in directories to treat them as packages. Without these:
```python
# This would fail without __init__.py:
from backend.app.services.llm import LLMService
```

### 4. **Git Hygiene**
Empty directories aren't tracked by git, so we use `.gitkeep` placeholder files to preserve the structure.

---

## Directory Structure Explained

### Backend Structure (`backend/`)

```
backend/
├── app/                          # Main Python package
│   ├── api/                      # API endpoints (routes)
│   │   └── __init__.py
│   ├── models/                   # Database tables (ORM models)
│   │   └── __init__.py
│   ├── schemas/                  # Request/response validation
│   │   └── __init__.py
│   ├── services/                 # Business logic layer
│   │   ├── llm/                  # Talk to OpenAI, Claude, Gemini
│   │   ├── cache/                # Semantic caching engine
│   │   ├── router/               # Choose which AI model to use
│   │   ├── execution/            # Run workflow stages
│   │   ├── analytics/            # Collect metrics
│   │   └── websocket/            # Real-time updates
│   ├── ml/                       # Machine learning models
│   │   └── __init__.py
│   └── utils/                    # Helper functions
│       └── __init__.py
├── alembic/                      # Database migrations
│   └── versions/                 # Migration files (empty now)
│       └── .gitkeep
└── tests/                        # Test suite
    └── __init__.py
```

#### What Each Backend Directory Does:

**`api/`** - API Route Handlers
- Contains endpoint definitions like `/workflows`, `/stages`, `/execute`
- Each file handles HTTP requests (GET, POST, PUT, DELETE)
- Example: `workflows.py` would handle workflow CRUD operations

**`models/`** - Database Schema
- SQLAlchemy ORM models that represent database tables
- Example: `Workflow` model = `workflows` table
- Defines columns, relationships, and constraints

**`schemas/`** - Data Validation
- Pydantic models for request/response validation
- Ensures incoming data is correct before processing
- Example: `WorkflowCreate` schema validates new workflow data

**`services/`** - Business Logic
- The "brain" of the application
- Each subdirectory handles a specific domain:
  - **`llm/`**: Abstraction layer for different AI providers
  - **`cache/`**: Semantic similarity search and caching
  - **`router/`**: Decides which AI model to use for each stage
  - **`execution/`**: Runs workflows, handles errors, retries
  - **`analytics/`**: Aggregates performance metrics
  - **`websocket/`**: Real-time status updates to frontend

**`ml/`** - Machine Learning Artifacts
- Pre-trained models for routing decisions
- Feature extraction logic
- Model metadata

**`alembic/`** - Database Migrations
- Tracks database schema changes over time
- Allows upgrading/downgrading database versions
- `versions/` contains migration scripts

**`tests/`** - Automated Tests
- Unit tests, integration tests
- Ensures code works as expected

### Frontend Structure (`frontend/`)

```
frontend/
├── src/
│   ├── api/                      # API client to talk to backend
│   │   └── .gitkeep
│   ├── pages/                    # Full page components
│   │   └── .gitkeep
│   ├── components/               # Reusable UI components
│   │   ├── ui/                   # Buttons, inputs, cards
│   │   ├── charts/               # Visualization components
│   │   ├── metrics/              # Metric display components
│   │   └── analytics/            # Analytics dashboard components
│   └── types/                    # TypeScript type definitions
│       └── .gitkeep
└── public/                       # Static assets (images, icons)
    └── .gitkeep
```

#### What Each Frontend Directory Does:

**`api/`** - Backend Communication
- Functions to call backend endpoints
- Example: `fetchWorkflows()`, `createWorkflow()`
- Handles authentication, error handling

**`pages/`** - Full Page Views
- Complete page components
- Example: `WorkflowsPage.tsx`, `DashboardPage.tsx`
- Each page is a route in the app

**`components/ui/`** - Reusable UI Elements
- Buttons, modals, forms, cards
- Styled with Tailwind CSS
- Used across multiple pages

**`components/charts/`** - Data Visualization
- Line charts, bar charts, pie charts
- Shows performance metrics, timing data

**`components/metrics/`** - Metric Displays
- Shows key performance indicators
- Cache hit rates, execution times, cost savings

**`components/analytics/`** - Analytics Views
- Complex analytics dashboards
- Combines multiple charts and metrics

**`types/`** - TypeScript Definitions
- Interface definitions for API responses
- Type safety throughout the frontend

---

## Configuration Files Explained

### 1. `.gitignore` - What NOT to Commit

Git tracks changes to files, but some files should NEVER be committed:

```gitignore
# Python compiled files - generated automatically
__pycache__/
*.pyc

# Virtual environments - each developer creates their own
.venv/
venv/

# Node modules - huge (100MB+), can be reinstalled
node_modules/

# Secret keys - NEVER commit these!
.env
.env.local

# Build outputs - generated from source code
frontend/dist/
*.egg-info/

# Database files - contain potentially sensitive data
*.db
*.sqlite3

# Large reference documents
PBL Project Planning for Sem-5.pdf
```

**Why this matters:**
- **Security**: Prevents accidentally committing API keys
- **Performance**: Keeps repo small and fast
- **Collaboration**: Each developer generates their own dependencies
- **Cleanliness**: Only source code is committed, not generated files

### 2. `README.md` - Project Documentation

The README is the first thing anyone sees when they visit the repository. Ours includes:

1. **Project Overview**: What the platform does
2. **Status Table**: What's complete, what's not
3. **Tech Stack**: All technologies used
4. **Directory Structure**: Visual guide to the codebase
5. **Quick Start**: How to run the project (added later)

**Key Section - Status Table:**
```markdown
| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Repo scaffold (MT-00) | ✅ Complete |
| Phase 1 | Workflow Manager (CRUD) | 🔲 Not started |
```

This gives anyone instant visibility into project progress.

### 3. `docker-compose.yml` - Multi-Service Orchestration

Docker Compose lets us run all services with one command:

```yaml
services:
  postgres:      # Database
  redis:         # Cache
  backend:       # FastAPI server
  frontend:      # React app
```

**Why Docker Compose?**
- **Consistency**: Same environment for all developers
- **Simplicity**: One command to start everything: `docker-compose up`
- **Isolation**: Services run in containers, don't conflict with local installs
- **Production-like**: Dev environment matches production

**Key Features in Our Setup:**

1. **Health Checks**: Wait for database to be ready before starting backend
2. **Environment Variables**: Passed from `.env` file
3. **Volume Mounts**: Code changes reflect immediately without rebuild
4. **Port Mapping**: Access services on localhost
5. **Dependencies**: Backend waits for postgres and redis

**Service Details:**

**PostgreSQL (Database)**
```yaml
postgres:
  image: postgres:15-alpine          # Official PostgreSQL image
  ports: ["5432:5432"]               # Standard PostgreSQL port
  environment:
    POSTGRES_USER: orchestrator
    POSTGRES_PASSWORD: orchestrator_dev
    POSTGRES_DB: ai_orchestrator
  healthcheck:                       # Wait until ready
    test: ["CMD-SHELL", "pg_isready"]
```

**Redis (Cache)**
```yaml
redis:
  image: redis:7-alpine              # Official Redis image
  ports: ["6379:6379"]               # Standard Redis port
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
```

**Backend (FastAPI)**
```yaml
backend:
  build: ./backend                   # Build from local Dockerfile
  ports: ["8000:8000"]               # API server port
  depends_on:                        # Wait for dependencies
    postgres:
      condition: service_healthy     # Wait until DB is ready
    redis:
      condition: service_healthy
  environment:
    - DATABASE_URL=postgresql+asyncpg://...
    - REDIS_URL=redis://redis:6379/0
    - OPENAI_API_KEY=${OPENAI_API_KEY}
```

**Frontend (React + Vite)**
```yaml
frontend:
  build: ./frontend                  # Build from local Dockerfile
  ports: ["5173:5173"]               # Vite dev server port
  depends_on: [backend]              # Backend must be running
  environment:
    - VITE_API_BASE_URL=http://localhost:8000
```

### 4. `.env.example` - Configuration Template

Environment variables store configuration that changes between environments (dev, staging, production).

**Why `.env.example` and not `.env`?**
- `.env` contains actual secrets → gitignored, never committed
- `.env.example` is a template → committed, shows what's needed
- Each developer copies `.env.example` to `.env` and fills in their keys

**Key Variable Categories:**

**Database Configuration**
```env
POSTGRES_USER=orchestrator           # Database username
POSTGRES_PASSWORD=orchestrator_dev   # Database password
POSTGRES_DB=ai_orchestrator          # Database name
DATABASE_URL=postgresql+asyncpg://...  # Full connection string
```

**Redis Configuration**
```env
REDIS_URL=redis://localhost:6379/0   # Redis connection string
```

**LLM API Keys** (the most sensitive!)
```env
OPENAI_API_KEY=sk-your-key-here      # OpenAI API key
ANTHROPIC_API_KEY=sk-ant-...         # Claude API key
GOOGLE_API_KEY=your-key-here         # Gemini API key
```

**Caching Configuration**
```env
CACHE_SIMILARITY_THRESHOLD=0.92      # 92% similar → cache hit
CACHE_TTL_SECONDS=86400              # 24 hours
```

**Execution Engine**
```env
MAX_RETRIES=3                        # Retry failed stages 3 times
STAGE_TIMEOUT_SECONDS=120            # 2 minute timeout per stage
```

---

## Git Setup Explained

### What is Git?

Git is a **version control system** that tracks changes to files over time. Think of it as:
- A time machine for your code
- A collaboration tool for teams
- A backup system with history

### Git Basics

**Repository (Repo)**: A project tracked by git
**Commit**: A snapshot of your code at a point in time
**Branch**: A parallel version of the code
**Remote**: A server hosting the repo (like GitHub)

### Why Initialize Git Now?

1. **Track Changes**: Every file creation, edit, deletion is tracked
2. **Collaboration**: Multiple developers can work simultaneously
3. **Backup**: Code is safe even if your computer crashes
4. **History**: See what changed, when, and why

### First Commit Strategy

Our first commit includes:
- ✅ Configuration files (`.gitignore`, `README.md`, etc.)
- ✅ All `__init__.py` files
- ✅ All `.gitkeep` files
- ❌ **NOT** the PDF (too large, not source code)
- ❌ **NOT** `.env` (contains secrets)
- ❌ **NOT** generated files (`__pycache__/`, `node_modules/`)

**Commit Message Format:**
```
MT-00: repo scaffold, .gitignore, README stub, docker-compose skeleton, .env.example
```

**Why this format?**
- Starts with task ID (`MT-00`)
- Lists what was done
- Clear and searchable in git history

---

## Step-by-Step Execution

Let me walk through exactly what each step does:

### Step 1: Create Directory Tree

**Command:**
```powershell
$dirs = @("backend/app/api", "backend/app/models", ...)
foreach ($d in $dirs) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
}
```

**What it does:**
- Creates 23 directories
- `-Force` creates parent directories if needed
- `-ItemType Directory` specifies folder (not file)
- `| Out-Null` suppresses output for cleaner logs

**Result:**
```
backend/
  app/
    api/       ← Created
    models/    ← Created
    services/
      llm/     ← Nested directory created
```

### Step 2: Create `__init__.py` Files

**Command:**
```powershell
$inits = @("backend/__init__.py", "backend/app/__init__.py", ...)
foreach ($f in $inits) {
  if (-not (Test-Path $f)) { 
    New-Item -ItemType File -Force -Path $f | Out-Null 
  }
}
```

**What it does:**
- Creates empty Python package marker files
- `-ItemType File` creates a file
- `Test-Path` checks if file already exists (don't overwrite)

**Why empty files?**
- Python just needs the file to exist
- Content can be added later if needed (package-level imports)

**What this enables:**
```python
# Now this import works:
from backend.app.services.llm import OpenAIProvider
```

### Step 3: Create `.gitkeep` Files

**Command:**
```powershell
$keeps = @("backend/alembic/versions/.gitkeep", ...)
foreach ($f in $keeps) {
  if (-not (Test-Path $f)) {
    New-Item -ItemType File -Force -Path $f | Out-Null
  }
}
```

**What it does:**
- Creates placeholder files in empty directories
- Allows git to track the directory structure

**Why needed?**
Git doesn't track empty directories. Without `.gitkeep`:
```
backend/alembic/versions/    ← Git ignores this (empty)
```

With `.gitkeep`:
```
backend/alembic/versions/
  .gitkeep                   ← Git tracks this
```

### Step 4: Create `.gitignore`

**What it does:**
Tells git which files to never track.

**Critical patterns:**
- `__pycache__/` - Python bytecode (auto-generated)
- `*.pyc` - Compiled Python files
- `.venv/` - Virtual environment (100MB+)
- `node_modules/` - NPM packages (can be 500MB+)
- `.env` - Secret keys (NEVER commit!)
- `*.db` - Database files (contain data)

**How git uses it:**
```bash
git status                  # Won't show __pycache__/
git add .                   # Won't add .env
git check-ignore .env       # Shows: .env (confirms it's ignored)
```

### Step 5: Create `README.md`

**What it does:**
Creates the project's front page.

**Key sections:**
1. **Title + Description**: What is this?
2. **Status Table**: What's done?
3. **Tech Stack**: What's it built with?
4. **Directory Structure**: Where is everything?
5. **Quick Start**: How to run it? (added later)

**Markdown format:**
```markdown
# Title (H1 - largest)
## Section (H2)
| Table | Header |  (Tables)
- Bullet point         (Lists)
```

### Step 6: Create `docker-compose.yml`

**What it does:**
Defines 4 services that work together.

**Service dependency chain:**
```
postgres + redis
    ↓
  backend
    ↓
  frontend
```

**Key concepts:**

**Volumes (persistent data):**
```yaml
volumes:
  postgres_data:              # Database persists between restarts
  redis_data:                 # Cache persists
```

**Port mapping (access from host):**
```yaml
ports:
  - "8000:8000"               # localhost:8000 → container:8000
```

**Environment variables (configuration):**
```yaml
environment:
  - DATABASE_URL=...          # Backend knows where database is
```

**Health checks (wait for ready):**
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready"]    # Check if PostgreSQL is ready
  interval: 10s                         # Check every 10 seconds
```

**Depends_on (start order):**
```yaml
depends_on:
  postgres:
    condition: service_healthy         # Wait until healthy
```

### Step 7: Create `.env.example`

**What it does:**
Documents every environment variable the project needs.

**Format:**
```env
# Comment explaining the variable
VARIABLE_NAME=default_value
```

**Developer workflow:**
```bash
# 1. Copy template
cp .env.example .env

# 2. Edit .env with real values
# OPENAI_API_KEY=sk-proj-abc123...

# 3. .env is gitignored, so keys stay secret
```

### Step 8: Git Initialize and First Commit

**Commands:**
```powershell
git init                               # Initialize repository
git add .gitignore                     # Stage file
git add README.md
...
git commit -m "MT-00: repo scaffold..."  # Create commit
```

**What each command does:**

**`git init`**
- Creates `.git/` directory
- Initializes version control
- Enables all git commands

**`git add <file>`**
- Stages file for commit
- File is ready to be snapshotted
- Can be unstaged with `git reset`

**`git commit -m "..."`**
- Creates a snapshot of staged files
- Records author, date, message
- Generates a unique hash (e.g., `a1b2c3d`)

**Verification:**
```powershell
git log --oneline -1                   # Shows last commit
# Output: a1b2c3d MT-00: repo scaffold...

git status                             # Shows working tree
# Output: nothing to commit, working tree clean
```

---

## Common Questions

**Q: Why so many directories if they're empty?**
A: It's easier to create them all now than remember where files should go later. Plus, `.gitkeep` preserves the structure.

**Q: Can I change the directory structure?**
A: Not recommended. Later micro-tasks expect this exact structure. Changes would break imports and references.

**Q: What if I don't have all three LLM API keys?**
A: You only need one to start. The platform will work with just OpenAI, or just Claude, etc.

**Q: Why PostgreSQL and not MySQL/SQLite?**
A: PostgreSQL has `pgvector` extension for semantic similarity search, which we need for caching.

**Q: Can I run this without Docker?**
A: Yes, but you'll need to install PostgreSQL and Redis locally. Docker is easier for consistent environments.

**Q: What's the difference between `DATABASE_URL` and `DATABASE_URL_SYNC`?**
A: 
- `DATABASE_URL`: Async driver (`asyncpg`) for FastAPI runtime
- `DATABASE_URL_SYNC`: Sync driver (`psycopg2`) for Alembic migrations

**Q: Why is the PDF gitignored?**
A: It's 2MB+ and not source code. Reference documents shouldn't be in the repo. Keep it locally or in cloud storage.

---

## Success Criteria

After MT-00, you should have:

✅ **23 directories** created  
✅ **15 `__init__.py` files** for Python packages  
✅ **10 `.gitkeep` files** for empty directories  
✅ **`.gitignore`** preventing junk commits  
✅ **`README.md`** documenting the project  
✅ **`docker-compose.yml`** defining all services  
✅ **`.env.example`** documenting configuration  
✅ **Git repository** initialized with first commit  
✅ **12 verification tests** all passing  

---

## What's Next: MT-01

After the scaffold is complete, MT-01 will:

1. Create `backend/app/main.py` - FastAPI application entry point
2. Create `backend/app/config.py` - Settings management
3. Create `backend/app/database.py` - Database connection
4. Create `backend/requirements.txt` - Python dependencies
5. Create `backend/Dockerfile` - Container build instructions

After MT-01, you can run:
```bash
uvicorn backend.app.main:app --reload
```

And visit `http://localhost:8000/docs` to see the API documentation!

---

## Visual Summary

```
MT-00: Repository Scaffold
│
├── Directory Structure (23 folders)
│   ├── backend/ (Python FastAPI server)
│   ├── frontend/ (React TypeScript app)
│   └── docs/ (Documentation)
│
├── Python Packages (15 __init__.py files)
│   └── Makes imports work
│
├── Git Placeholders (10 .gitkeep files)
│   └── Preserves empty directories
│
├── Configuration Files
│   ├── .gitignore (what NOT to commit)
│   ├── README.md (project overview)
│   ├── docker-compose.yml (service orchestration)
│   └── .env.example (configuration template)
│
└── Version Control
    └── git init + first commit
```

**End of MT-00 Explanation** 🎉
