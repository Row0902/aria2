---
name: pydantic-sdk
description: "Trigger: pydantic, BaseModel, TypedDict, discriminated union, validator, model_config, serialization, data modeling. Pydantic patterns for SDKs — models, validation, schemas, and serialization."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Modeling structured responses from the aria2 JSON-RPC API
- Defining TypedDicts for raw data or BaseModel for validated data
- Using discriminated unions for variant responses (download status)
- Validating and coercing incoming data from the daemon
- Converting camelCase response keys to snake_case Python attributes
- Serializing models for output or debugging

## Critical Patterns

### BaseModel vs TypedDict — When to Use Each

```python
# TypedDict — lightweight, runtime-accessible keys, no validation
class FileInfo(TypedDict):
    index: str
    path: str
    length: str
    selected: str

# BaseModel — validation, coercion, methods, serialization
class DownloadStatusResponse(BaseModel):
    gid: str
    status: DownloadStatus
    total_length: str  # All numeric fields are strings (aria2 convention)
```

| Use TypedDict | Use BaseModel |
|---|---|
| Simple passive data containers | Data that needs validation |
| Dict-like access is natural | Methods or computed fields needed |
| No Pydantic overhead needed | Discriminated unions |
| Performance-critical paths | Serialization/deserialization |

The project uses **both**: TypedDicts for simple response types and BaseModel for complex structures (download status variants).

### Handling aria2's String-Numeric Fields

aria2 returns all numeric values as strings. **Never convert to int in models** — convert at the user's call site:

```python
class DownloadStatusResponse(BaseModel):
    total_length: str      # "1048576", not 1048576
    download_speed: str    # "102400"
    connections: str       # "4"

# User converts when needed
size = int(status.total_length)
```

### Field Aliases for camelCase → snake_case

aria2 returns camelCase keys. Convert with `Field(alias=...)`:

```python
from pydantic import Field

class FileInfo(BaseModel):
    index: str
    path: str
    length: str
    completed_length: str = Field(alias="completedLength")
    selected: str

    model_config = ConfigDict(populate_by_name=True)
```

With `populate_by_name=True`, users can access both `completed_length` and `completedLength`.

### Discriminated Unions

Use when a response can be one of several shapes (aria2's `tellStatus` returns different fields per state):

```python
from pydantic import BaseModel, Discriminator, Tag, TypeAdapter
from typing import Annotated, Union

# Variant models
class _ActiveStatus(BaseModel):
    status: Literal["active"] = "active"
    total_length: str
    download_speed: str
    connections: str

class _CompleteStatus(BaseModel):
    status: Literal["complete"] = "complete"
    total_length: str
    download_speed: str = "0"
    upload_speed: str = "0"

def _status_discriminator(v: Any) -> str:
    if isinstance(v, dict):
        return v.get("status", "active")
    if hasattr(v, "status"):
        return v.status
    return "active"

DownloadStatusResult = Annotated[
    Union[_ActiveStatus, _CompleteStatus],
    Discriminator(_status_discriminator),
]

# Usage
adapter = TypeAdapter(DownloadStatusResult)
parsed = adapter.validate_python(raw_data)
```

### Field Validators

```python
from pydantic import field_validator

class _BaseDownloadStatus(BaseModel):
    status: DownloadStatus
    gid: str

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> str:
        """Accept both string and enum values."""
        if isinstance(v, DownloadStatus):
            return v.value
        return str(v).lower()
```

### Model Config

```python
class Aria2Model(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,      # Accept both alias and field name
        extra="ignore",             # Ignore extra fields from daemon
        frozen=False,               # Allow mutation
        validate_default=True,      # Validate default values
    )
```

### Partial Responses

aria2 supports a `keys` parameter to filter response fields. Models should handle missing keys gracefully:

```python
class PartialStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    gid: str
    status: DownloadStatus = DownloadStatus.ACTIVE
    total_length: str = "0"
    error_message: str | None = None
```

### Serialization

```python
user = User(id=1, name="test")

# To dict
user.model_dump()                    # {'id': 1, 'name': 'test'}
user.model_dump(by_alias=True)       # {'id': 1, 'name': 'test'}
user.model_dump(exclude_none=True)   # Exclude None values

# To JSON
user.model_dump_json()               # '{"id":1,"name":"test"}'
user.model_dump_json(indent=2)

# To python (for type conversion)
parsed = DownloadStatusResponse.model_validate(data)
```

### TypeAdapter for One-Off Parsing

When you don't need a full model class:

```python
from pydantic import TypeAdapter

# Parse a list of files
FileList = TypeAdapter(list[FileInfo])
files = FileList.validate_python(raw_data)

# Parse a union
Result = TypeAdapter(Union[DownloadStatusResponse, Aria2Error])
result = Result.validate_python(data)
```

### Generic Models

```python
from typing import Generic, TypeVar

T = TypeVar("T")

class RpcResponse(BaseModel, Generic[T]):
    jsonrpc: str = "2.0"
    result: T | None = None
    error: RpcError | None = None
    id: int = 0

# Usage
resp = RpcResponse[str].model_validate({"result": "abc123"})
```

## Best Practices for SDKs

### 1. Mirror API semantics
If the upstream API uses strings for numbers, keep them as strings. Don't coerce — it hides precision.

### 2. Use alias for camelCase
aria2 returns camelCase. Model with `Field(alias=...)` and `populate_by_name=True`.

### 3. Prefer strict validation
Set `extra="forbid"` or `"ignore"` to avoid silent field drift with API changes.

### 4. Discriminated unions for variant responses
When a response shape depends on a field value, use `Discriminator`.

### 5. Document None fields
Mark optional fields explicitly: `error_message: str | None = None`.

### 6. Exclude internal fields from serialization
```python
class Model(BaseModel):
    _internal: dict[str, Any] = PrivateAttr(default_factory=dict)
```

### 7. Keep models focused
One model per response type. Don't cram all fields into one class.

## Common Pitfalls

- **Coercing int fields**: aria2 returns "1048576" not 1048576. Store as `str`.
- **Missing `populate_by_name`**: Without it, users can't set fields by snake_case name.
- **Discriminator without catch-all**: If the discriminator function doesn't handle unknown statuses, it crashes.
- **Validation on the hot path**: `BaseModel` validation has overhead. Consider TypedDict for high-throughput paths.
- **`extra="forbid"` vs `"ignore"`**: `forbid` catches API drift but breaks on unknown fields. `ignore` is safer for SDKs.

## Commands

```bash
uv run python -c "from pydantic import __version__; print(__version__)"
```

## Resources

- Pydantic docs: <https://docs.pydantic.dev/>
- Discriminated unions: <https://docs.pydantic.dev/latest/concepts/unions/>
- TypeAdapter: <https://docs.pydantic.dev/latest/api/type_adapter/>
- Field: <https://docs.pydantic.dev/latest/concepts/fields/>
