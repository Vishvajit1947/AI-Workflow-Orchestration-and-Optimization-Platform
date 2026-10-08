# MT-02 Technical Explanation: Database ORM Models

## Overview

MT-02 establishes the foundational data models for the AI Workflow Orchestrator using SQLAlchemy ORM. These models define how workflows, stages, and their dependencies are represented in the database and manipulated in Python code.

---

## Architecture

### Three-Model Schema

```
┌─────────────┐
│  Workflow   │
│  (parent)   │
└──────┬──────┘
       │ 1:N
       │ cascade
       ↓
┌─────────────┐
│    Stage    │
│   (child)   │
└──────┬──────┘
       │ 1:N
       │ self-referential
       ↓
┌──────────────────┐
│ StageDependency  │
│  (join table)    │
└──────────────────┘
```

---

## Model-by-Model Breakdown

### 1. Workflow Model

**Purpose:** Represents a complete multi-stage AI workflow that users create and execute.

**Key Fields:**
- `id`: UUID primary key (database-generated)
- `name`: Human-readable workflow name (max 255 chars)
- `description`: Optional long-form description
- `objective`: Optional statement of what the workflow should accomplish
- `status`: Current execution status (draft/running/completed/failed/paused)
- `created_at`, `updated_at`: Automatic timestamps

**Relationships:**
- `stages`: One-to-many relationship with Stage model
  - Uses `cascade="all, delete-orphan"` so deleting a workflow deletes all stages
  - Orders stages by `stage_order` field
  - Uses `lazy="selectin"` for efficient async loading

**Why These Choices:**
- **UUID over integer IDs**: Globally unique, no collisions in distributed systems
- **String status**: Easier to evolve than PostgreSQL ENUM (no migration for new statuses)
- **Cascade delete**: Ensures data integrity (no orphaned stages)
- **Description vs Objective**: Description is metadata; objective is semantic (used by AI)

---

### 2. Stage Model

**Purpose:** Represents a single executable step within a workflow.

**Key Fields:**
- `id`: UUID primary key
- `workflow_id`: Foreign key to parent workflow (cascade delete)
- `name`: Stage name
- `instruction`: The prompt/instruction for the AI to execute
- `stage_order`: Integer for explicit ordering (allows reordering)
- `stage_type`: Optional categorization (analysis, design, generation, etc.)
- `model_preference`: Optional hint for which LLM to use
- `config`: JSONB field for flexible stage-specific configuration
- `status`: Execution status (pending/running/completed/failed/skipped/cached)

**Relationships:**
- `workflow`: Many-to-one with Workflow
- `dependencies`: One-to-many with StageDependency (stages this stage depends on)
- `dependents`: One-to-many with StageDependency (stages that depend on this stage)

**Why These Choices:**
- **stage_order**: Allows explicit ordering independent of creation order
- **JSONB config**: Flexible key-value store without schema changes
  - Example: `{"temperature": 0.7, "max_tokens": 2000, "retry_count": 3}`
- **Bidirectional dependencies**: Navigate both "what do I need?" and "who needs me?"
- **Nullable stage_type**: Not all stages fit categories; custom workflows possible

---

### 3. StageDependency Model

**Purpose:** Tracks dependencies between stages (which stages must complete before others can start).

**Key Fields:**
- `id`: UUID primary key
- `stage_id`: The stage that has a dependency
- `depends_on_stage_id`: The stage that must complete first
- `dependency_type`: Type of dependency (sequential, merge)

**Constraints:**
- Unique constraint on `(stage_id, depends_on_stage_id)` prevents duplicate dependencies

**Relationships:**
- `stage`: Many-to-one with Stage (the dependent stage)
- `depends_on_stage`: Many-to-one with Stage (the prerequisite stage)

**Why These Choices:**
- **Explicit join table**: Could use many-to-many, but explicit table allows metadata (dependency_type)
- **Unique constraint**: Prevents duplicate relationships
- **dependency_type field**: Enables different execution patterns:
  - `sequential`: Standard "wait for completion"
  - `merge`: Advanced use case (wait for multiple stages to merge results)

---

## Key Technical Decisions

### 1. SQLAlchemy 2.0 Syntax

Uses modern `Mapped[type]` type hints:
```python
name: Mapped[str] = mapped_column(String(255), nullable=False)
```

**Benefits:**
- Type safety with mypy/pyright
- Better IDE autocomplete
- Clearer intent (nullable vs required)

### 2. Server-Side UUID Generation

```python
id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    server_default=func.gen_random_uuid(),  # Database generates
    default=uuid.uuid4,                      # Python fallback
)
```

**Why:**
- Database ensures uniqueness even across distributed transactions
- Python fallback for cases where object created before insert
- `gen_random_uuid()` is PostgreSQL's built-in UUID function

### 3. Timezone-Aware Timestamps

```python
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now()
)
```

**Why:**
- `timezone=True` stores UTC timestamps
- `server_default=func.now()` lets database set timestamp (consistent across clients)
- `onupdate=func.now()` auto-updates `updated_at` on every change

### 4. Cascade Deletes

```python
ForeignKey("workflows.id", ondelete="CASCADE")
```

**Why:**
- Deleting a workflow automatically deletes all stages (no orphans)
- Deleting a stage automatically deletes all dependencies
- Database enforces referential integrity
- Cleaner than manual cleanup in application code

### 5. JSONB for Config

```python
config: Mapped[dict] = mapped_column(
    JSONB,
    default=dict,
    server_default="{}"
)
```

**Why:**
- PostgreSQL JSONB is indexed and queryable
- No schema migration needed for new config options
- Each stage type can have different config structure
- Example configs:
  ```json
  {"temperature": 0.7, "max_tokens": 2000}
  {"retry_count": 3, "timeout": 300}
  {"output_format": "markdown", "include_code": true}
  ```

### 6. Lazy Loading Strategy

```python
stages: Mapped[list["Stage"]] = relationship(
    "Stage",
    lazy="selectin",
    ...
)
```

**Why:**
- `lazy="selectin"` loads related objects in a single additional query
- Avoids N+1 query problem
- Works well with async SQLAlchemy
- Alternative `lazy="joined"` would use LEFT OUTER JOIN (heavier)

---

## Circular Import Handling

In `stage.py`, there's an intentional circular import:

```python
# At top: from backend.app.database import Base

class Stage(Base):
    workflow: Mapped["Workflow"] = relationship(...)  # String forward reference

# After Stage definition:
from backend.app.models.workflow import Workflow  # noqa: E402

class StageDependency(Base):
    ...  # Can now use Workflow type directly
```

**Why This Works:**
1. Stage uses string forward reference `"Workflow"` (not evaluated at import time)
2. After Stage is defined, import Workflow
3. SQLAlchemy resolves string references after all models loaded
4. `# noqa: E402` suppresses linter warning about import not at top

---

## Relationship Patterns

### One-to-Many (Workflow → Stages)

```python
# In Workflow:
stages: Mapped[list["Stage"]] = relationship(
    "Stage",
    back_populates="workflow",
    cascade="all, delete-orphan"
)

# In Stage:
workflow: Mapped["Workflow"] = relationship(
    "Workflow",
    back_populates="stages"
)
```

**Navigation:**
```python
workflow = await session.get(Workflow, workflow_id)
for stage in workflow.stages:
    print(stage.name)
```

### Self-Referential Many-to-Many (Stage Dependencies)

```python
# In Stage:
dependencies: Mapped[list["StageDependency"]] = relationship(
    "StageDependency",
    foreign_keys="StageDependency.stage_id",  # Which FK to use
    back_populates="stage"
)

dependents: Mapped[list["StageDependency"]] = relationship(
    "StageDependency",
    foreign_keys="StageDependency.depends_on_stage_id",  # Other FK
    back_populates="depends_on_stage"
)
```

**Navigation:**
```python
stage = await session.get(Stage, stage_id)

# What does this stage need?
for dep in stage.dependencies:
    prerequisite = dep.depends_on_stage
    print(f"Must wait for: {prerequisite.name}")

# What depends on this stage?
for dep in stage.dependents:
    dependent = dep.stage
    print(f"Blocks: {dependent.name}")
```

---

## Usage Examples

### Creating a Workflow with Stages

```python
from backend.app.models import Workflow, Stage, StageDependency

# Create workflow
workflow = Workflow(
    name="Code Review Workflow",
    description="Automated code review with AI",
    objective="Review Python code for bugs and style issues",
    status="draft"
)

# Create stages
analyze = Stage(
    workflow=workflow,
    name="Analyze Code",
    instruction="Analyze the provided Python code for logical errors",
    stage_order=1,
    stage_type="analysis",
    config={"max_tokens": 2000}
)

review = Stage(
    workflow=workflow,
    name="Style Review",
    instruction="Check code style against PEP 8",
    stage_order=2,
    stage_type="review",
    config={"strict_mode": True}
)

# Create dependency: review depends on analyze
dep = StageDependency(
    stage=review,
    depends_on_stage=analyze,
    dependency_type="sequential"
)

# Save all (cascade saves stages and dependencies)
async with async_session_factory() as session:
    session.add(workflow)
    await session.commit()
```

### Querying Workflows

```python
# Get workflow with stages
result = await session.execute(
    select(Workflow).where(Workflow.id == workflow_id)
)
workflow = result.scalar_one()

# Stages automatically loaded (lazy="selectin")
print(f"Workflow: {workflow.name}")
for stage in workflow.stages:
    print(f"  Stage {stage.stage_order}: {stage.name}")
```

### Checking Stage Dependencies

```python
stage = await session.get(Stage, stage_id)

# Can this stage run?
can_run = all(
    dep.depends_on_stage.status == "completed"
    for dep in stage.dependencies
)

if can_run:
    stage.status = "running"
    await session.commit()
```

---

## Testing Strategy

The verification tests ensure:

1. **Import Test**: All models import without errors
2. **Metadata Test**: Alembic can discover tables via `Base.metadata`
3. **Relationship Tests**: SQLAlchemy correctly configured bidirectional relationships

These are unit-level tests that verify ORM configuration, not database functionality (that comes in MT-03 after migrations).

---

## Future Extensions

This schema supports future enhancements:

1. **Stage Results Storage**: Add `result` JSONB field to Stage
2. **Execution History**: Add `StageExecution` model for run history
3. **Workflow Templates**: Add `is_template` boolean to Workflow
4. **Stage Retries**: Add `retry_count`, `max_retries` to Stage
5. **Parallel Execution**: Use dependency_type="merge" for fan-out/fan-in patterns
6. **Conditional Stages**: Add `condition` field for dynamic workflow branching

---

## Common Patterns

### Soft Deletes (Not Implemented, but Easy to Add)

```python
deleted_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

Then filter: `select(Workflow).where(Workflow.deleted_at.is_(None))`

### Audit Trail (Not Implemented, but Easy to Add)

```python
created_by: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
)
```

### Versioning (Not Implemented, but Easy to Add)

```python
version: Mapped[int] = mapped_column(Integer, default=1)
```

Use optimistic locking: `UPDATE ... WHERE id = ? AND version = ?`

---

## Summary

MT-02 delivers a robust, extensible ORM schema that:
- Uses modern SQLAlchemy 2.0 patterns
- Leverages PostgreSQL features (UUID, JSONB, CASCADE)
- Supports complex workflow dependencies
- Provides bidirectional navigation
- Enables future extensions without schema changes (via JSONB)

These models form the data backbone for the entire AI Orchestrator platform.
