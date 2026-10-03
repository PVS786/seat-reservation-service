---

name: code-review
description: Performs focused engineering reviews of application, database, API, concurrency, security, testing, and operational changes. Use when reviewing a diff, pull request, implementation, refactor, or correctness-sensitive change before acceptance.
---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Code Review

## Purpose

Review changes for correctness, maintainability, security, reliability, and unintended behavior.

The review should identify concrete problems and meaningful risks rather than provide a generic summary or stylistic commentary.

Priorities:

1. Correctness
2. Security
3. Reliability
4. Concurrency safety
5. Data integrity
6. Maintainability
7. Performance
8. Style

Do not report issues merely because a different implementation could be preferred.

---

## Review Process

For a meaningful change:

1. Understand the intended behavior.
2. Identify the relevant requirements and invariants.
3. Inspect the complete change and surrounding code.
4. Trace the important execution paths.
5. Consider concurrent and failure scenarios.
6. Check tests and whether they demonstrate the intended behavior.
7. Report concrete findings.
8. Distinguish confirmed defects from suggestions or uncertainties.

Do not review only the changed lines when surrounding code affects correctness.

---

## Finding Severity

Use these categories:

### Critical

A likely production failure, security vulnerability, data corruption risk, or correctness violation affecting a core invariant.

### High

A significant bug or race condition that can produce incorrect behavior under realistic conditions.

### Medium

A meaningful reliability, maintainability, performance, or edge-case problem that should be addressed.

### Low

A minor issue with limited practical impact.

### Suggestion

An optional improvement that is not required for correctness.

Do not inflate severity.

---

## Reservation Review

For any change affecting reservation behavior, verify:

* seat ownership remains exclusive;
* per-user limits remain enforced under concurrency;
* idempotency remains correct;
* multi-seat requests remain atomic;
* cancellation remains safe;
* reconciliation remains valid;
* expected conflicts remain domain-level errors.

Ask:

```text id="mvr2yu"
What happens if two requests execute simultaneously?
What happens if one transaction rolls back?
What happens if the response is lost after commit?
What happens if the client retries?
What happens if cancellation races with reservation?
```

For multiple resource locks, verify that lock acquisition ordering is deterministic.

---

## Transaction Review

For each transaction-sensitive change, identify:

* transaction start;
* state read;
* state protected by locks or constraints;
* validation;
* state mutation;
* commit;
* rollback behavior.

Check for:

* check-then-act races;
* partial commits;
* missing rollback;
* unnecessarily long transactions;
* unrelated I/O inside transactions;
* hidden transaction boundaries;
* state changes occurring outside the intended transaction.

Do not assume a single application statement is atomic without verifying the underlying database behavior.

---

## Concurrency Review

Consider at least:

### Same resource

```text
multiple users → same seat
```

### Same user

```text
multiple requests → same show/user
```

### Same idempotency key

```text
multiple requests → same key
```

### Multiple resources

```text
multiple requests → overlapping seat sets
```

### Conflicting lifecycle operations

```text
reserve ↔ cancel
```

Check whether concurrent execution can produce:

* duplicate ownership;
* limit violations;
* duplicate reservations;
* lost updates;
* stale decisions;
* partial state;
* deadlocks.

Do not consider async/await itself a concurrency-safety mechanism.

---

## Idempotency Review

Verify:

* the idempotency key has an explicit scope;
* durable uniqueness protects concurrent requests;
* the original logical request can be identified;
* a same-key/same-request retry does not create a new reservation;
* a same-key/different-request retry is rejected;
* a transaction that rolls back does not leave stale idempotency state;
* a committed operation remains replayable after a lost response.

Check that idempotency behavior is enforced by durable state rather than process memory.

---

## Database Review

Check:

### Data modeling

* each field has a clear purpose;
* authoritative state is not unnecessarily duplicated;
* relationships are represented correctly;
* nullable fields have justified semantics.

### Constraints

Look for appropriate:

* primary keys;
* foreign keys;
* uniqueness;
* composite uniqueness;
* non-null constraints;
* domain checks.

### Queries

Check:

* parameterization;
* appropriate filtering;
* correct transaction context;
* unnecessary queries;
* possible N+1 behavior;
* query ordering;
* index usage for important access paths.

### Migrations

Verify:

* schema changes are represented by migrations;
* migrations are reproducible;
* destructive changes are deliberate;
* models and migrations remain consistent.

---

## API Review

Check:

* request validation;
* authentication;
* authorization;
* HTTP method semantics;
* status codes;
* error responses;
* response consistency;
* unexpected data exposure.

For identity-sensitive operations, verify that identity comes from authenticated context rather than a client-controlled request field.

Check ownership enforcement for cancellation and other user-specific operations.

---

## Security Review

Look for:

* authentication bypass;
* authorization bypass;
* user identity spoofing;
* unsafe SQL construction;
* secret leakage;
* sensitive information in logs;
* overly permissive endpoints;
* unsafe error details;
* missing input validation.

Do not treat authentication as sufficient without verifying authorization.

---

## Async and Runtime Review

Check that:

* asynchronous request handlers do not perform unexpected blocking I/O;
* database clients match the async execution model;
* shared mutable application state is not used unsafely;
* manual threads/processes/background workers are justified;
* connection usage is compatible with request concurrency.

Do not recommend threads, processes, or additional workers simply because request volume is high.

First identify the actual bottleneck.

---

## Error Handling Review

Verify the distinction between:

### Expected business outcomes

Examples:

```text id="ft8xj7"
seat unavailable
booking limit exceeded
idempotency conflict
```

These should produce intentional domain responses.

### Unexpected failures

Examples:

```text id="wl32jc"
database failure
unexpected exception
programming error
```

These should remain observable and should not be silently converted into successful-looking responses.

Look for overly broad exception handlers.

---

## Observability Review

For behavior that matters operationally, check:

* useful structured logs;
* request/correlation ID;
* appropriate metrics;
* meaningful metric labels;
* health endpoint;
* readiness/dependency checks;
* useful error context.

Avoid high-cardinality metric labels such as arbitrary user IDs or request IDs.

---

## Testing Review

Check whether tests demonstrate behavior rather than only implementation details.

For correctness-sensitive changes, look for tests covering:

* happy path;
* invalid input;
* authorization;
* business conflicts;
* retries;
* rollback;
* concurrency;
* cancellation;
* reconciliation.

A unit test that mocks away the database cannot by itself prove database concurrency correctness.

For concurrency behavior, prefer integration testing against a real database.

---

## Performance Review

Do not optimize based on assumptions.

Look for clear issues such as:

* unnecessary database round trips;
* unbounded queries;
* excessive transaction duration;
* avoidable blocking operations;
* inefficient connection usage;
* missing indexes for established access patterns.

Do not trade correctness for speculative performance improvements.

---

## Maintainability Review

Look for:

* unnecessary abstractions;
* duplicated business logic;
* unclear ownership of state;
* hidden side effects;
* confusing control flow;
* excessive configuration;
* unnecessary dependencies;
* unrelated changes mixed into a feature.

Prefer focused, cohesive changes.

---

## Review Output

Start with the most important findings.

For every actionable finding, provide:

```text id="52r2se"
Severity
Location
Problem
Why it matters
Recommended fix
```

Example:

```text
High — reservation_service.py:84

Problem:
The availability check occurs before the seat row is protected.

Why it matters:
Two concurrent transactions can both observe AVAILABLE and subsequently confirm the same seat.

Recommended fix:
Move the availability decision inside the transaction and protect the seat using the approved concurrency mechanism.
```

Do not bury serious findings inside a long list of minor style comments.

If no significant issues are found, say so clearly and identify the areas that were specifically checked.

Do not claim a change is correct solely because tests pass.

---

## Review Boundaries

Do not:

* rewrite the entire implementation during review;
* introduce unrelated architectural changes;
* demand abstractions without a concrete need;
* flag purely stylistic preferences as defects;
* modify tests solely to suppress a review finding.

When a problem requires a design decision rather than a straightforward fix, explain the trade-off and leave the final decision to the developer.

---

## Review Workflow

Use this sequence:

```text id="5j7c3u"
understand requirement
→ identify invariants
→ inspect changed code
→ trace important paths
→ consider concurrency/failure
→ inspect tests
→ report findings
```

For correctness-sensitive changes, explicitly challenge at least:

* concurrent duplicate requests;
* concurrent conflicting requests;
* rollback;
* retry after timeout;
* cancellation interaction;
* authorization boundaries.
