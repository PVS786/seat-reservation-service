---

name: implementation-style
description: Produces and refactors clear, maintainable Python and FastAPI code for this service. Use when implementing features, refactoring code, improving readability, or deciding how application logic should be structured.
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Implementation Style

## Purpose

Produce clear, maintainable application code with predictable behavior and minimal unnecessary complexity.

Priorities:

1. Correctness
2. Clarity
3. Simplicity
4. Testability
5. Maintainability
6. Performance where justified

---

## General Style

Prefer:

* clear control flow;
* descriptive names;
* focused functions;
* explicit dependencies;
* explicit error handling;
* type hints;
* simple data structures;
* consistent project conventions.

Avoid:

* unnecessary indirection;
* deeply nested logic;
* oversized functions or classes;
* speculative abstractions;
* unnecessary inheritance;
* design patterns without a concrete requirement;
* duplicate helper layers;
* magic values;
* hidden side effects;
* clever code that reduces readability.

Use the simplest implementation that satisfies the requirements and preserves the existing architecture.

---

## Structure and Responsibility

Keep responsibilities clear:

```text
HTTP layer
    ↓
application/service logic
    ↓
persistence
```

Route handlers should focus on HTTP concerns such as:

* request parsing;
* authentication context;
* validation;
* response construction.

Business rules should live in appropriate service/application logic.

Persistence concerns should remain separated from HTTP-specific behavior.

Do not introduce additional layers unless they provide a concrete benefit.

---

## Function Design

Prefer functions with:

* one clear responsibility;
* explicit inputs and outputs;
* limited branching;
* minimal hidden state.

Avoid functions that combine unrelated responsibilities such as:

* authentication;
* validation;
* transaction management;
* business logic;
* persistence;
* HTTP response formatting;

unless the combination is genuinely small and clear.

Keep critical business flows easy to follow from entry point to state change.

---

## Classes and Abstractions

Create a class when it represents meaningful state or a coherent responsibility.

Do not create classes solely to wrap functions.

Avoid unnecessary abstractions such as generic repositories, factories, managers, or abstract base classes when there is only one concrete implementation and no requirement for substitution.

Prefer a small number of cohesive components over many thin layers.

Introduce an abstraction when it:

* removes meaningful duplication;
* isolates a meaningful boundary;
* improves testability;
* represents a real domain responsibility;
* or addresses a demonstrated change requirement.

---

## Python Style

Use modern, idiomatic Python.

Prefer:

* type hints;
* clear function signatures;
* Pydantic models at API boundaries;
* standard library functionality where appropriate;
* enums for constrained domain states where they improve clarity.

Avoid:

* unnecessary metaprogramming;
* dynamic behavior that obscures control flow;
* overly clever comprehensions;
* excessive lambdas;
* exception-driven normal control flow.

Use comprehensions when they improve readability; use ordinary loops when the logic is more complex.

---

## FastAPI Style

Keep route handlers focused and thin.

Typical flow:

```text
request
→ validate
→ authenticate
→ call application logic
→ return response
```

Use FastAPI dependencies for cross-cutting concerns such as authentication and request context.

Keep business logic independent of FastAPI-specific response handling where practical.

Do not introduce middleware, dependencies, or abstractions unless they solve a real application concern.

---

## Async Code

Use `async`/`await` for I/O-bound operations when the underlying library supports asynchronous APIs.

Use asynchronous database and HTTP clients consistently within asynchronous request paths.

Do not introduce asynchronous constructs solely for stylistic reasons.

Do not introduce manual threads, processes, task pools, or background workers without a concrete requirement or demonstrated workload.

Remember:

```text
async concurrency
≠
business-state concurrency
```

Async allows efficient handling of concurrent I/O. It does not replace database transactions, constraints, or locking required for correctness.

---

## Error Handling

Represent expected business outcomes explicitly.

Examples include:

```text
seat already taken
per-user limit exceeded
idempotency conflict
reservation not found
reservation ownership conflict
```

Map these to deliberate domain/API responses.

Do not use broad exception handling to hide unexpected failures.

Avoid:

```python
except Exception:
    ...
```

unless there is a specific reason and the original failure remains observable.

Infrastructure and programming errors should remain diagnosable.

---

## Transactions

Keep important transaction boundaries visible.

For correctness-critical operations, the code should make the sequence of operations understandable:

```text
begin
→ protect required state
→ validate
→ modify state
→ commit
```

Avoid hiding critical transaction behavior behind generic utilities that make atomicity difficult to reason about.

Keep unrelated external I/O outside critical database transactions.

---

## Concurrency-Critical Code

Prefer explicit sequencing over compressed or opaque database operations.

When an ordering or locking rule is important, document the reason briefly.

Example:

```python
# Lock requested seats in deterministic order to avoid lock-order conflicts.
```

Comments should explain non-obvious engineering decisions rather than restate the code.

Do not use process-local state as a correctness mechanism for persistent shared state.

---

## Comments

Write comments primarily for:

* concurrency decisions;
* transaction boundaries;
* non-obvious business rules;
* important trade-offs;
* workarounds for external or framework behavior.

Avoid comments that merely describe obvious syntax or repeat the code.

Prefer self-explanatory names and structure over excessive comments.

---

## Constants and Configuration

Avoid magic values in business logic.

Use named constants or configuration for meaningful configurable values such as:

* booking limits;
* timeouts;
* metric names;
* domain status values.

Do not create configuration for values that have no legitimate need to vary.

Keep secrets and environment-specific settings outside source control.

---

## Dependencies

Prefer existing project dependencies.

Before adding a dependency, consider:

* whether it is necessary;
* whether existing libraries already provide the capability;
* maintenance cost;
* security implications;
* whether it simplifies or complicates the system.

Do not add a dependency for trivial functionality.

---

## Refactoring

When implementing a feature:

1. Understand the existing implementation.
2. Reuse established project patterns where appropriate.
3. Make the smallest coherent change.
4. Avoid unrelated cleanup.
5. Preserve existing behavior unless the requirement changes it.

If a refactor changes transaction boundaries, concurrency behavior, persistence semantics, or API contracts, treat it as a correctness-sensitive change and test it accordingly.

---

## Testing

Add or update tests with behavior changes.

Tests should cover:

* normal behavior;
* validation;
* business conflicts;
* failure behavior;
* relevant concurrency cases;
* authorization;
* persistence effects.

Prefer behavior-focused tests over tests designed only to increase coverage.

Do not change tests merely to accommodate an implementation that violates the documented requirements.

---

## Agent Workflow

For implementation tasks:

```text
inspect
→ understand existing patterns
→ identify the smallest appropriate change
→ implement
→ add/update tests
→ run tests
→ review the diff
```

Before a substantial change, briefly identify any new:

* dependency;
* abstraction;
* transaction boundary;
* async boundary;
* persistence behavior.

Avoid introducing any of these without a concrete reason.

After implementation, report:

* what changed;
* which tests were run;
* any important implementation considerations;
* any unresolved issues.
