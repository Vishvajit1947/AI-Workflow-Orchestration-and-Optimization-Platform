# MT-04 Technical Explanation: Pydantic Schemas

## Purpose
This document explains the design decisions, patterns, and technical details of the Pydantic schemas implemented in MT-04.

## Architecture Overview

### Schema Organization
```
backend/app/schemas/
├── __init__.py          # Central re-export point
├── common.py            # Shared/generic schemas
├── workflow.py          # Workflow-specific schemas
└── stage.py             # Stage and dependency schemas
```

This modular structure:
- **Separates concerns**: Each domain model has its own schema file
- **Enables selective imports**: Services can import only what they need
- **Simplifies maintenance**: Changes to one domain don't affect others
- **Provides clear entry point**: `__init__.py` offers convenient imports

## Schema Design Patterns

### 1. Base-Create-Update-Read Pattern

Each domain follows this structure:

```python
# Base: Shared fields for Create and Read
class WorkflowBase(BaseModel):
    name: str
    description: Optional[str]
    objective: Optional[str]

# Create: Inherits Base, adds creation-specific fields
class WorkflowCreate(WorkflowBase):
    pass  # Uses all Base fields

# Update: All fields optional for partial updates
class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

# Read: Extends Base with DB-generated fields
class WorkflowRead(WorkflowBase):
    id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    stages: list[StageReadBrief] = []
    
    model_config = {"from_attributes": True}
```

**Why this pattern?**
- **DRY principle**: Base classes eliminate duplication
- **Type safety**: Different operations have different field requirements
- **Partial updates**: Update schemas allow PATCH operations
- **Clear semantics**: Schema name indicates its purpose

### 2. Brief vs Full Representations

```python
# Brief: Minimal info for embedding/listing
class StageReadBrief(BaseModel):
    id: uuid.UUID
    name: str
    stage_order: int
    stage_type: Optional[str]
    status: str

# Full: Complete details with relationships
class StageRead(StageBase):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    dependencies: list[StageDependencyRead] = []
```

**Benefits:**
- **Performance**: List endpoints don't load unnecessary relationships
- **Nested representations**: `WorkflowRead` embeds `StageReadBrief` without circular dependencies
- **Flexibility**: Different endpoints can choose appropriate detail level

### 3. Generic Pagination Schema

```python
T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    skip: int
    limit: int
    has_more: bool
```

**Type-safe pagination:**
```python
# At runtime, fully typed:
PaginatedResponse[WorkflowListItem]
PaginatedResponse[StageRead]
```

This provides:
- **Reusability**: One schema for all paginated endpoints
- **Type safety**: IDE autocomplete and type checking
- **Consistent API**: All paginated responses have the same structure

## Validation Rules Explained

### Field-Level Validation

#### 1. String Length Constraints
```python
name: str = Field(..., min_length=1, max_length=255)
```
- **min_length=1**: Prevents empty strings (whitespace-only still possible, can add regex if needed)
- **max_length=255**: Matches database VARCHAR(255) constraints
- **`...` (Ellipsis)**: Indicates required field

#### 2. Pattern Matching for Enums
```python
status: Optional[str] = Field(None, pattern="^(draft|running|completed|failed|paused)$")
```
- **Regex pattern**: Enforces exact match to allowed values
- **Alternative**: Could use Python Enum, but strings are more flexible for DB storage
- **Fail fast**: Invalid status rejected at API boundary, not in DB layer

#### 3. Numeric Constraints
```python
stage_order: int = Field(default=0, ge=0)
```
- **ge=0**: Greater than or equal to 0 (no negative orders)
- **default=0**: Sensible default for new stages

#### 4. Nested Lists with Defaults
```python
dependencies: list[StageDependencyCreate] = Field(default_factory=list)
```
- **default_factory=list**: Creates new list per instance (avoids mutable default pitfall)
- **Allows empty lists**: Stages can have zero dependencies

### Model-Level Configuration

```python
model_config = {"from_attributes": True}
```

**Why needed?**
- Enables ORM compatibility: Pydantic can read from SQLAlchemy model attributes
- Without it: `StageRead.model_validate(stage_orm_object)` would fail
- With it: Automatic conversion from ORM models to Pydantic schemas

## Relationship Handling

### One-to-Many: Workflow → Stages

```python
# In WorkflowRead
stages: list[StageReadBrief] = []
```

**Design decisions:**
- **Brief representation**: Avoids loading full stage details unnecessarily
- **Default empty list**: Workflows without stages still serialize correctly
- **Lazy loading friendly**: Service layer controls if/when to load stages

### One-to-Many: Stage → Dependencies

```python
# In StageCreate
dependencies: list[StageDependencyCreate] = Field(default_factory=list)

# In StageRead
dependencies: list[StageDependencyRead] = []
```

**Two-way representation:**
- **Create**: Client provides dependency IDs to create
- **Read**: Server returns full dependency objects with their IDs

### Preventing Circular Dependencies

**Problem:** Workflow contains Stages, Stage references Workflow
**Solution:** Use brief representations and careful schema design

```python
# WorkflowRead uses StageReadBrief (no workflow_id reference back)
class WorkflowRead(WorkflowBase):
    stages: list[StageReadBrief] = []

# StageRead references workflow_id but not full Workflow object
class StageRead(StageBase):
    workflow_id: uuid.UUID  # Just the ID, not nested object
```

## Partial Updates with exclude_unset

```python
class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
```

**Usage in service layer:**
```python
# Client sends: {"name": "New Name"}
update_data = WorkflowUpdate(**request.json())
update_dict = update_data.model_dump(exclude_unset=True)
# Result: {"name": "New Name"}  (description and status excluded)

# Apply partial update to ORM model
for key, value in update_dict.items():
    setattr(orm_obj, key, value)
```

**Benefits:**
- **True PATCH semantics**: Only update provided fields
- **Preserves null vs unset**: Can distinguish between "set to null" and "don't change"
- **Database efficiency**: Only modified columns trigger updates

## Examples Field for API Documentation

```python
name: str = Field(..., examples=["Software Development Workflow"])
```

**Purpose:**
- **OpenAPI/Swagger docs**: Examples appear in interactive API documentation
- **Developer experience**: Shows realistic usage
- **Testing**: Provides copy-paste examples for manual testing

## Type Hints and IDE Support

All schemas use modern Python type hints:

```python
from typing import Optional
from datetime import datetime
import uuid

class StageRead(StageBase):
    id: uuid.UUID              # IDE knows this is UUID
    workflow_id: uuid.UUID
    status: str
    created_at: datetime       # IDE knows datetime methods available
    dependencies: list[StageDependencyRead] = []  # IDE provides list operations
```

**Developer benefits:**
- **Autocomplete**: IDEs suggest available fields and methods
- **Type checking**: mypy/pyright catch type errors before runtime
- **Refactoring**: Rename fields safely across codebase

## Common Pitfalls Avoided

### 1. Mutable Default Arguments ❌
```python
# WRONG - all instances share same list!
class StageCreate(BaseModel):
    dependencies: list[StageDependencyCreate] = []
```

```python
# CORRECT - each instance gets own list
class StageCreate(BaseModel):
    dependencies: list[StageDependencyCreate] = Field(default_factory=list)
```

### 2. Missing from_attributes ❌
```python
# WRONG - can't convert from ORM
class WorkflowRead(WorkflowBase):
    id: uuid.UUID
    # Missing: model_config = {"from_attributes": True}
```

```python
# CORRECT
class WorkflowRead(WorkflowBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}
```

### 3. Inconsistent Optional Fields ❌
```python
# WRONG - required in Base, but sometimes null from DB
class WorkflowBase(BaseModel):
    description: str  # Not Optional
```

```python
# CORRECT - matches DB schema allowing NULL
class WorkflowBase(BaseModel):
    description: Optional[str] = None
```

## Integration with FastAPI

These schemas will integrate seamlessly with FastAPI endpoints:

```python
@router.post("/workflows", response_model=WorkflowRead)
async def create_workflow(
    workflow: WorkflowCreate,
    db: Session = Depends(get_db)
):
    # FastAPI automatically:
    # 1. Validates request body against WorkflowCreate schema
    # 2. Converts to WorkflowCreate instance
    # 3. Returns WorkflowRead (validates response)
    # 4. Generates OpenAPI docs with examples
    
    # Service layer handles business logic
    return workflow_service.create(db, workflow)
```

**Automatic features:**
- Request validation
- Response serialization
- OpenAPI schema generation
- Interactive API docs (Swagger UI)
- Type-safe request/response handling

## Testing Strategy

The 5 verification tests validate:

1. **Import resolution**: All schemas accessible via `backend.app.schemas`
2. **Valid creation**: Schemas accept valid data
3. **Validation rejection**: Schemas reject invalid data (empty names)
4. **Nested objects**: Complex schemas with relationships work
5. **Partial updates**: `exclude_unset=True` behaves correctly

This ensures:
- **No import errors**: Python module structure correct
- **Validation works**: Pydantic rules enforced
- **Edge cases handled**: Empty strings, partial updates, nested lists

## Performance Considerations

### Schema Validation Overhead
- **Minimal**: Pydantic uses Rust-based core (pydantic-core) for performance
- **Cached**: Schema validation logic compiled once, reused
- **Worth it**: Catching errors at API boundary prevents DB exceptions

### Serialization Performance
```python
# Fast: Direct ORM to Pydantic with from_attributes
workflow_read = WorkflowRead.model_validate(workflow_orm)

# Also fast: Dict to Pydantic
workflow_read = WorkflowRead(**workflow_dict)
```

### Large List Responses
- **Use brief schemas**: `WorkflowListItem` instead of `WorkflowRead`
- **Pagination**: `PaginatedResponse` limits result sets
- **Lazy loading**: Service layer controls relationship loading

## Future Extensibility

The schema design supports future enhancements:

### 1. Additional Validation
```python
from pydantic import field_validator

class WorkflowCreate(WorkflowBase):
    @field_validator('name')
    def name_must_not_be_reserved(cls, v):
        if v.lower() in ['admin', 'system']:
            raise ValueError('Reserved workflow name')
        return v
```

### 2. Computed Fields
```python
from pydantic import computed_field

class WorkflowRead(WorkflowBase):
    @computed_field
    @property
    def is_complete(self) -> bool:
        return self.status == 'completed'
```

### 3. Serialization Customization
```python
from pydantic import field_serializer

class WorkflowRead(WorkflowBase):
    @field_serializer('created_at')
    def serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()
```

## Conclusion

The MT-04 schema implementation provides:
- **Type-safe request/response handling**
- **Clear separation between create/update/read operations**
- **Flexible validation rules**
- **ORM compatibility**
- **Efficient serialization**
- **Excellent developer experience**

These schemas form the foundation for all API interactions in the PBL AI Orchestrator, ensuring data integrity from the API boundary through to the database layer.

---
**Related Documents:**
- MT-04-COMPLETION-SUMMARY.md
- MT-04-TEST-RESULTS.md
- MT-02-EXPLANATION.md (ORM Models)
