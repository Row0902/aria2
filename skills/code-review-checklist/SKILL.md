---
name: code-review-checklist
description: "Trigger: code review, PR review, review checklist, audit, PR checklist, review SDK, pull request review. Structured code review checklist for Python SDKs — types, errors, docs, tests, API surface."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Reviewing pull requests before merging
- Preparing a PR for review (self-review)
- Auditing code for consistency and correctness
- Checking SDK-specific patterns (error wrapping, transport lifecycle, public API)
- Ensuring documentation and tests are complete

## Critical Patterns

### PR Readiness (before review)

- [ ] PR title follows conventional commits (`feat:`, `fix:`, etc.)
- [ ] PR description explains **what** and **why** (not how)
- [ ] Related issues linked (`Closes #N`)
- [ ] Branch is rebased on main (no merge commits)
- [ ] CI passes (lint, type-check, test)
- [ ] No unrelated changes in the diff

### General Checklist

#### 1. Behavioral Correctness
- [ ] Does the code do what the PR description says?
- [ ] Are edge cases handled (empty input, None, zero, max values)?
- [ ] Are error states tested (connection failure, timeout, invalid input)?
- [ ] Are there no silent data corruptions?
- [ ] Is concurrency handled correctly (shared state, locks, tasks)?

#### 2. SDK Public API
- [ ] Is the public API consistent with existing patterns?
- [ ] Are new methods named with snake_case (Python convention)?
- [ ] Are type annotations complete and correct?
- [ ] Is `__all__` updated in `__init__.py`?
- [ ] Are new exceptions added to the error hierarchy?
- [ ] Are `**kwargs` avoided in public methods?

#### 3. Error Handling
- [ ] Are third-party exceptions wrapped in `Aria2Error` subclasses?
- [ ] Do `Raises` in docstrings match actual raised exceptions?
- [ ] Is `raise ... from e` used to preserve chain?
- [ ] Are error messages informative (include context, not just "error")?
- [ ] Is idempotent `close()` safe to call multiple times?

#### 4. Async Patterns
- [ ] Are `async with` context managers supported where appropriate?
- [ ] Are background tasks tracked and cancelled on close?
- [ ] Are timeouts applied to all external calls?
- [ ] Is `asyncio.CancelledError` handled correctly (not swallowed)?
- [ ] Are `await` expressions inside `except` blocks guarded?

#### 5. Type Safety (ty)
- [ ] Does `ty check src/` pass with no new errors?
- [ ] Are `Any` annotations minimized?
- [ ] Are generic types used where appropriate?
- [ ] Are `cast()` calls justified with a comment?
- [ ] Are `ty: ignore` comments justified and minimal?

#### 6. Code Quality (ruff)
- [ ] Does `ruff check src/` pass?
- [ ] Does `ruff format --check src/` pass?
- [ ] Are there no `F401` (unused import) or `F841` (unused variable)?
- [ ] Is import ordering correct (I rules)?

#### 7. Documentation
- [ ] Do new public methods have Google-style docstrings?
- [ ] Is the module-level docstring present (for new modules)?
- [ ] Does the summary line use imperative mood?
- [ ] Are `Args:`, `Returns:`, `Raises:` documented?
- [ ] Does the `CHANGELOG.md` have an `[Unreleased]` entry?

#### 8. Testing
- [ ] Are there tests for new functionality?
- [ ] Do tests cover success, error, and edge cases?
- [ ] Are async tests using `pytest-asyncio` (not `asyncio.run`)?
- [ ] Are mocks used appropriately (not over-mocked)?
- [ ] Do tests clean up resources (close transports, stop servers)?
- [ ] Is the test file named `test_<module>.py`?

#### 9. Dependencies
- [ ] Are new dependencies justified?
- [ ] Are dependencies pinned with minimum version?
- [ ] Are dev dependencies in the right group (not runtime)?
- [ ] Is `uv.lock` updated?

#### 10. Security
- [ ] Are secrets (tokens, passwords) never logged?
- [ ] Are `token:`-prefixed parameters masked in logs?
- [ ] Are URLs/URIs validated if user-provided?
- [ ] Is there no `eval()`, `exec()`, `pickle.loads()` of untrusted data?

### SDK-Specific Review Areas

#### Transport Layer
```python
# Review: new transport implementation
- [ ] Does it implement the Transport ABC?
- [ ] Is `connect()` idempotent?
- [ ] Is `close()` safe to call multiple times?
- [ ] Are exceptions wrapped in SDK errors?
- [ ] Does it handle connection refused, timeout, DNS failure?
```

#### Client Methods
```python
# Review: new RPC method
- [ ] Does method name match Python conventions (snake_case)?
- [ ] Does it delegate to `_request()` for transport?
- [ ] Are params correctly constructed (including secret)?
- [ ] Is the response parsed into a model?
- [ ] Is the method documented with Args/Returns/Raises?
```

#### Models (Pydantic/TypedDict)
```python
# Review: new model
- [ ] Are numeric fields typed as `str` (aria2 convention)?
- [ ] Are camelCase aliases set with `Field(alias=...)`?
- [ ] Is `populate_by_name = True` in ConfigDict?
- [ ] Is `extra = "ignore"` set?
- [ ] Are optional fields marked `| None` with `= None` default?
```

#### Event Callbacks
```python
# Review: new event registration
- [ ] Does the callback signature match the event data?
- [ ] Are callback exceptions isolated (not propagated)?
- [ ] Is the event registered in `_EVENT_MAP`?
- [ ] Is the notification parsed before dispatch?
```

### Review Comments Style

When leaving review feedback:

```text
✅ Constructive:
  "Consider wrapping this httpx error in Aria2ConnectionError
   so users get consistent SDK exceptions."

❌ Vague:
  "This is wrong."

✅ Specific:
  "Line 42: `except Exception` is too broad. Catch specific
   httpx exception types instead."

✅ Reference:
  "This breaks the Transport ABC contract. `connect()`
   should not raise on WS failure — see sdk-design skill."
```

### Review Priority Order

Review in this order for maximum efficiency:

1. **Public API surface** (method signatures, types, docstrings)
2. **Error handling** (exception wrapping, edge cases)
3. **Async patterns** (cancellation, timeouts, lifecycle)
4. **Tests** (do they actually test the claimed behavior?)
5. **Documentation** (does it match the code?)
6. **Code quality** (style, naming, unused code)

## Best Practices

### 1. Review in small batches
PRs under 400 lines get better reviews. Split large PRs.

### 2. Start with the public API
Check method signatures, types, and docstrings before implementation details.

### 3. Read tests first
Tests tell you what the author intended. If tests don't make sense, the implementation won't either.

### 4. Question inconsistencies
If a new method doesn't follow the pattern of existing methods, ask why.

### 5. Say "consider" not "fix"
Phrase suggestions as options unless they're clear bugs or security issues.

### 6. Approve with confidence, request changes when unsure
If you don't understand the change, request clarification. Approve only when you're confident.

## Common Findings in SDK Reviews

1. **Leaking 3rd-party exceptions**: `httpx`, `websockets`, `json` exceptions not wrapped
2. **Missing error handling**: Connection errors, timeouts not caught
3. **No timeout on RPC calls**: External calls without `asyncio.timeout()`
4. **Shared mutable state**: Module-level variables modified by async functions
5. **Callback exceptions crash the reader loop**: Missing `try/except` in `_emit()`
6. **Overly broad exceptions**: `except Exception` catching `asyncio.CancelledError`
7. **Missing `__all__`**: Public API not explicitly declared
8. **No changelog entry**: New feature without documentation

## Resources

- Google code review guidelines: <https://google.github.io/eng-practices/review/>
- Conventional commits: <https://www.conventionalcommits.org/>
- Python style guide: <https://peps.python.org/pep-0008/>
- Ruff rules: <https://docs.astral.sh/ruff/rules/>
