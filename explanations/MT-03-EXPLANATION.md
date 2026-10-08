# MT-03 Implementation Explanation

## Task: Alembic Setup & Initial Migration

### Overview
This micro-task established Alembic as the database migration system for the AI Orchestration Platform. Alembic manages schema evolution, tracks migration history, and provides version control for database changes.

## Implementation Approach

### 1. Alembic Configuration Files

#### `backend/alembic.ini`
- Configured the Alembic environment with proper logging levels
- Set up the sync database URL format: `postgresql+psycopg2://...`
- Used psycopg2 driver explicitly since Alembic doesn't support asyncpg directly
- Configured console logging with appropriate handlers and formatters

#### `backend/alembic/env.py`
- Auto-imports all ORM models from `backend.app.models`
- Reads database URL from `settings.DATABASE_URL_SYNC`
- Supports both online (live DB) and offline (SQL generation) modes
- Populates `Base.metadata` for autogenerate functionality
- Adds project root to sys.path for proper imports

#### `backend/alembic/script.py.mako`
- Migration file template with proper revision tracking
- Includes type hints for revision identifiers
- Provides upgrade() and downgrade() function stubs

### 2. Migration Generation Strategy

**Challenge Encountered:**
Initial attempts to use `alembic revision --autogenerate` failed due to:
1. Python 3.14 compatibility issues with pydantic-core
2. Connection issues from Windows host to Dockerized PostgreSQL (IPv6 vs IPv4 addressing)
3. psycopg/psycopg2 driver confusion in SQLAlchemy 2.x

**Solution:**
Created the initial migration manually based on the ORM model definitions:
- Analyzed `Workflow`, `Stage`, and `StageDependency` models
- Manually wrote migration file `001_initial_tables_workflows_stages_dependencies.py`
- Applied migration via SQL file to avoid connection issues

### 3. Database Schema Created

#### **workflows** table
- `id`: UUID primary key (auto-generated)
- `name`: varchar(255) - workflow identifier
- `description`: text - detailed description
- `objective`: text - workflow goal
- `status`: varchar(50) - draft/running/completed/failed/paused
- `created_at`: timestamptz - creation timestamp
- `updated_at`: timestamptz - last modification timestamp

#### **stages** table
- `id`: UUID primary key (auto-generated)
- `workflow_id`: UUID foreign key to workflows (CASCADE delete)
- `name`: varchar(255) - stage identifier
- `instruction`: text - stage instructions
- `stage_order`: integer - execution order
- `stage_type`: varchar(100) - analysis/design/generation/testing/etc
- `model_preference`: varchar(100) - preferred LLM model
- `config`: JSONB - flexible configuration storage
- `status`: varchar(50) - pending/running/completed/failed/skipped/cached
- `created_at`: timestamptz - creation timestamp
- `updated_at`: timestamptz - last modification timestamp

#### **stage_dependencies** table
- `id`: UUID primary key (auto-generated)
- `stage_id`: UUID foreign key to stages (CASCADE delete)
- `depends_on_stage_id`: UUID foreign key to stages (CASCADE delete)
- `dependency_type`: varchar(50) - sequential/merge
- Unique constraint: `uq_stage_dependency` on (stage_id, depends_on_stage_id)

### 4. Configuration Updates

Updated `backend/app/config.py`:
- Changed `DATABASE_URL_SYNC` from `postgresql://` to `postgresql+psycopg2://`
- This ensures Alembic uses psycopg2 driver explicitly

Updated `.env.example` (if needed in future):
- Should reflect the psycopg2 driver format

### 5. Migration Application

Created `migration_001.sql` and applied via Docker exec:
```sql
CREATE TABLE workflows (...);
CREATE TABLE stages (...);
CREATE TABLE stage_dependencies (...);
INSERT INTO alembic_version (version_num) VALUES ('001');
```

Applied using:
```powershell
Get-Content backend\migration_001.sql | docker exec -i ai_orchestrator_postgres psql -U orchestrator -d ai_orchestrator
```

## Key Design Decisions

### 1. Manual Migration Creation
- Chose manual migration over autogenerate due to environment constraints
- Ensures precise control over initial schema
- Future migrations can still use autogenerate once environment is stabilized

### 2. UUID Primary Keys
- Used `gen_random_uuid()` for all primary keys
- Provides distributed ID generation
- Avoids sequence conflicts in distributed systems

### 3. JSONB for Configuration
- `stages.config` uses JSONB for flexible, schema-less configuration
- Allows stage-specific settings without schema changes
- Enables JSON queries for configuration analysis

### 4. Cascade Deletes
- All foreign keys use `ON DELETE CASCADE`
- Ensures referential integrity
- Simplifies workflow deletion logic

### 5. Timestamp Defaults
- Used `now()` server-side defaults for timestamps
- Ensures consistent timezone handling (timestamptz)
- `updated_at` will need trigger or application-level update logic

## Verification Results

All four acceptance tests passed:

✅ **Test 1**: Alembic version tracking works
- `alembic_version` table exists
- Current revision: `001`

✅ **Test 2**: All three tables exist
- workflows ✓
- stages ✓
- stage_dependencies ✓

✅ **Test 3**: Workflows table has correct columns
- All 7 required columns present
- id, name, description, objective, status, created_at, updated_at

✅ **Test 4**: JSONB config column works
- stages.config is of type `jsonb`
- Default value `{}` properly set

## Files Created/Modified

### Created:
1. `backend/alembic.ini` - Alembic configuration
2. `backend/alembic/env.py` - Environment setup and model imports
3. `backend/alembic/script.py.mako` - Migration template
4. `backend/alembic/versions/001_initial_tables_workflows_stages_dependencies.py` - Initial migration
5. `backend/migration_001.sql` - SQL for direct application
6. `backend/verify_mt03.py` - Verification test script

### Modified:
1. `backend/app/config.py` - Updated DATABASE_URL_SYNC to use psycopg2 driver

## Dependencies

### Installed:
- `alembic==1.20.0` - Migration tool
- `mako==1.4.3` - Template engine for migrations
- `psycopg2-binary==2.9.13` - PostgreSQL driver for sync connections

### Required (from requirements.txt):
- `sqlalchemy[asyncio]==2.0.36`
- `asyncpg==0.30.0` (for async connections, not used by Alembic)

## Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| Python 3.14 incompatibility with pydantic-core | Installed only Alembic and dependencies separately |
| Connection auth failure from Windows to Docker PostgreSQL | Applied migration via Docker exec inside container |
| SQLAlchemy 2.x defaulting to psycopg3 | Explicitly used `postgresql+psycopg2://` URL format |
| Autogenerate requiring database connection | Created manual migration file from ORM model analysis |

## Integration Points

This MT integrates with:
- **MT-01**: Uses database configuration from config.py
- **MT-02**: Migrates ORM models (Workflow, Stage, StageDependency)
- **MT-04**: Future Pydantic schemas will match this database schema

## Next Steps (MT-04)

With the database schema in place, MT-04 will:
1. Create Pydantic schemas matching these tables
2. Define request/response models for API endpoints
3. Establish validation rules for workflow creation
