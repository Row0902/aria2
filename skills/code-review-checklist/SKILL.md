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

#### 5. Type Safety (ty) — Strict Rules
- [ ] Does `ty check src/` pass with **no new errors**? (Strict: all rules at error level, no warnings tolerated)
- [ ] Are `Any` annotations minimized? (Each `Any` is a type hole — justify with a comment)
- [ ] Are generic types used where appropriate (``Generic[T]``, ``TypeVar``, ``ParamSpec``)?
- [ ] Are `cast()` calls justified with a comment explaining why the type narrow is safe?
- [ ] Are `ty: ignore` comments justified and minimal? (Each one documents the upstream limitation)

> **Project policy**: `strict_types: true` — ``ty`` runs at maximum strictness.
> Invalid argument types, unresolved imports, and unused awaitables all fail the build.
> See ``pyproject.toml`` ``[tool.ty.rules]``.

#### 6. Code Quality (ruff)
- [ ] Does `ruff check src/` pass?
- [ ] Does `ruff format --check src/` pass?
- [ ] Are there no `F401` (unused import) or `F841` (unused variable)?
- [ ] Is import ordering correct (I rules)?

#### 7. Documentation — Strict Docstrings (Google convention)
- [ ] Do new public methods have Google-style docstrings?
- [ ] Is the module-level docstring present (for new modules)?
- [ ] Does the summary line use **imperative mood**? (``"Return"`` not ``"Returns"``, ``"Connect"`` not ``"Connects"``)
- [ ] Are ``Args:``, ``Returns:``, ``Raises:`` documented?
- [ ] Are blank lines correct after each section header? (D413 enforced)
- [ ] Does the ``CHANGELOG.md`` have an ``[Unreleased]`` entry?

> **Project policy**: `strict_docstrings: true` — D102, D401, D413 enforced at error level
> via ruff with Google convention. D107 (``__init__``) and D105 (magic methods) are excluded.
> See ``pyproject.toml`` ``[tool.ruff.lint.pydocstyle]``.

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

#### 11. Design Principles — Maximum Cohesion & Zero Coupling

Each item includes a **review maneuver** — a concrete action to detect violations while reading the diff.

##### Cohesion — Is each piece focused?

- [ ] Does each module/class have exactly one well-defined responsibility?
  → **Maneuver**: Try to rename the file or class to something more specific. If you can find a better name, it's doing too much. If you can't, it's focused.
- [ ] Can you describe what the module does in one sentence without "and"?
  → **Maneuver**: Write that sentence. The moment "and" appears, you've found multiple concerns.
- [ ] Are methods cohesive — do all operations within a method serve one goal?
  → **Maneuver**: Read the method body. Can you extract a meaningful sub-method with a clear name? If yes, the method is doing multiple things.
- [ ] Are there no "god classes", "god modules", or "god functions"?
  → **Maneuver**: Count public methods. >10 on one class is a smell unless strongly justified. For functions, count parameters: >4 is a smell.
- [ ] Is related behavior grouped together (not scattered across files)?
  → **Maneuver**: Run `git diff --stat`. One feature touching 5+ unrelated files signals low cohesion at the package level.
- [ ] Is unrelated behavior kept separate?
  → **Maneuver**: `grep -r "from.*utils import" src/` or `grep -r "from.*helpers import" src/` — these modules accumulate unrelated concerns by nature.
- [ ] **Package cohesion (REP/CCP/CRP)**: Are the classes in this package released, closed, and reused together?
  → **Maneuver**: Check whether a consumer imports only one class from a package and ignores the rest. That class likely belongs in a different package.

##### Coupling — Are dependencies minimal?

- [ ] Do modules depend on abstractions, not concrete implementations?
  → **Maneuver**: Look for `from x import XConcreteClass` where the module instantiates it directly. Could it depend on a Protocol or ABC instead?
- [ ] Can you change internal implementation without changing consumers?
  → **Maneuver**: Check for `@property` or public getters that exist only to let external modules read internal state. Those are leaky abstractions.
- [ ] Is the public API surface minimal?
  → **Maneuver**: Compare `__all__` (or public symbols by convention) against what consumers actually use. Anything unused but public is future coupling.
- [ ] Are there no cyclical dependencies?
  → **Maneuver**: `grep -r "from module_a import" module_b/ && grep -r "from module_b import" module_a/` — if both hit, there's a cycle.
- [ ] Do imports reflect genuine conceptual dependencies?
  → **Maneuver**: For each import, ask: could this module work without it? If a module pulls a heavy library for one utility, consider extracting.
- [ ] Would a change cascade across unrelated modules? (shotgun surgery)
  → **Maneuver**: Search for callers of the changed function. If they span 3+ unrelated modules, the function is coupled to too many contexts.
- [ ] **Tell Don't Ask / Feature Envy**: Does a method query another object's state and then decide what to do?
  → **Maneuver**: Find methods that call `.get_X()` or read a property from a *different* object and then branch on the value. The decision logic should live on the object that owns the data.
- [ ] **Law of Demeter**: Are there chains like `a.b.c.d`?
  → **Maneuver**: Grep for 3+-dot chains accessing attributes (not fluent API calls). Each dot couples to the intermediate object's structure.
- [ ] **Control coupling**: Is a flag or string passed to switch another module's internal behavior?
  → **Maneuver**: Search for parameter names `mode`, `type`, `kind`, `format`, `style`, `strategy`. These signal that the caller dictates internal logic instead of the callee owning it.

##### Connascence Framework — A vocabulary for coupling severity

When you find a dependency between two elements, classify its *connascence type*. This gives you a shared vocabulary in reviews and a clear severity scale:

| Connascence | Severity | What it means | How to spot in review | Action |
|---|---|---|---|---|
| **Name** | Weakest | Two modules must agree on a name (constant, function, class) | `from x import TIMEOUT` — both must use the same name | ✅ Acceptable if naming is consistent |
| **Type** | Weak | Two modules must agree on a type | A function returns `int`, caller expects `int` | ✅ Acceptable if types are explicit |
| **Meaning** | Moderate | A value carries implicit meaning | `if status == 2` — what is 2? | ❌ Extract to named constant or enum |
| **Position** | Moderate | Argument order matters | `func(a, b, c)` — caller must get order right | ❌ Use keyword args or dataclass for ≥3 params |
| **Algorithm** | Strong | Two modules implement same algorithm independently | Date parsing in two places, both must agree on format | ❌ Centralize into one shared function |
| **Execution** | Strong | Operation order matters between modules | `await connect()` must run before `await send()` | ❌ Use a protocol/context manager to enforce order |

**How to use in review**: When you write "this is tightly coupled", take an extra second to name the connascence type. "This is connascence of meaning — the `2` should be `DownloadStatus.COMPLETED`." It raises the bar from opinion to shared vocabulary.

##### Zero Coupling Realism

Zero literal coupling is impossible — components must communicate. The goal is:

- Coupling through **stable interfaces** (Protocols, ABCs, typed contracts)
- Coupling that is **explicit, visible, and justified** in the import statement
- **No** control coupling, content coupling, or cyclical dependencies
- **No** cascading coupling — a change in A does not force changes in B, C, D
- The weakest connascence type (Name, Type) that gets the job done

#### 12. Strict Single-Responsibility & LoC Thresholds

Enforced by ``wc-lint.py`` in pre-commit and CI.  Each threshold has a
**review implication** beyond what the tool can check.

- [ ] **File ≤ 200 lines** — every file stays under 200 lines of actual code
   (comments and docstrings excluded from the spirit of the rule).
   → **Maneuver**: If a file exceeds this, it likely has multiple concerns.
     Extract one concern to a new module.
   → **Critical** at 500 lines — merge blocker.
- [ ] **Function ≤ 20 lines** — every function/method body stays under 20 lines.
   → **Maneuver**: Count blank lines + comments + code.  At 15 lines, it's
     time to extract helper functions.
   → Exceptions: ``__init__`` with many attribute assignments, ``match``
     statements with exhaustive arms.
- [ ] **Class ≤ 10 public methods** — no class exposes more than 10 public
   methods (non-``_``-prefixed).
   → **Maneuver**: Count the public methods.  If >10, the class has more
     than one responsibility — split into sub-managers.
   → See ``Aria2Client`` as the reference pattern (delegates to
     ``DownloadManager``, ``StatusManager``, etc.).
- [ ] **Strict single-responsibility**: every module, class, function,
   method, and package has exactly one well-defined responsibility.
   → **Maneuver**: Write a one-sentence purpose for each.  If "and"
     appears, split.
   → The tool (``wc-lint``) enforces structural limits.  The reviewer
     enforces the *semantic* limit — does this unit do ONE thing?

> **Project policy**: All thresholds enforced by ``wc-lint.py`` at pre-commit
> and CI.  See ``openspec/config.yaml`` ``quality.*``.

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
- [ ] **Strict polymorphic validation**: Does this model represent a variant (different shapes by status/type)?
   → Use Pydantic ``Discriminator`` with ``Tag()`` instead of Optional fields.
   → Every variant gets its own model, selected by a discriminator field.
   → Never use a single model with many ``Optional`` fields to represent variant data.

> **Project policy**: `strict_polymorphic_validation: true` — every variant data structure
> MUST use Pydantic discriminated unions (``Annotated[Union[...], Discriminator(...)]``).
> Single models with Optional fields for variant data are rejected in review.
> See ``DownloadStatusResponse`` in ``aria2/models/download_response.py`` for the reference pattern.
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
9. **Low cohesion**: A class or module that does unrelated things (e.g., a `Client` class that also formats output)
10. **High coupling**: Importing internal helpers from another module instead of going through its public API
11. **Cyclical imports**: Module A imports from B, and B imports from A (creates tight coupling and initialization order bugs)
12. **Leaky abstraction**: Internal implementation details exposed as public methods or properties
13. **Shotgun surgery**: A single conceptual change touches 4+ unrelated files — sign of low cohesion in the design
14. **Control coupling via mode flags**: A parameter named `mode`, `type`, `kind`, `format`, or `strategy` that switches internal behavior of the callee. The caller dictates logic instead of the module owning its behavior — invert control.
15. **Feature Envy**: A method spends more time querying another object's data than operating on its own. Classic sign: a method that calls `.get_x()` or reads properties from a *different* object repeatedly.
16. **Law of Demeter violations**: Chains like `response.data.items[0].name` couple the caller to the entire data shape of `response`, `data`, and `items`. A change in any intermediate structure breaks the chain.
17. **Connascence of meaning**: Magic values (`if x == 3`, `if status == "C"`) that both producer and consumer must agree on without a shared named constant. Each magic value is a time bomb.

## Resources

- Google code review guidelines: <https://google.github.io/eng-practices/review/>
- Conventional commits: <https://www.conventionalcommits.org/>
- Python style guide: <https://peps.python.org/pep-0008/>
- Ruff rules: <https://docs.astral.sh/ruff/rules/>
