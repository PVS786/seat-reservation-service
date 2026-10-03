---

name: reservation-correctness
description: Designs, implements, reviews, and extends reservation behavior while preserving concurrency safety, transactional consistency, idempotency, per-user booking limits, seat ownership, cancellation semantics, and reconciliation invariants. Use for reservation, booking, seat allocation, cancellation, idempotency, locking, concurrency, transaction, race-condition, or high-contention changes.
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Reservation Correctness

## Purpose

This skill governs correctness-critical work in the seat-reservation domain.

The goal is not simply to make the API work for normal requests. The system must remain correct under concurrent requests, retries, cancellations, transaction failures, process restarts, and future feature extensions.

Priorities:

1. Correctness
2. Explicit concurrency reasoning
3. Transactional consistency
4. Simplicity
5. Testability
6. Maintainability
7. Performance supported by measurement

Do not optimize for architectural sophistication.

---

## Before Making a Change

For reservation-related changes, first inspect:

1. `docs/requirements.md`
2. `docs/architecture.md`
3. `docs/decisions.md`
4. relevant application code
5. relevant tests

Before changing correctness-critical behavior, briefly identify:

* the invariant being protected;
* the shared state involved;
* the transaction boundary;
* how concurrent requests interact;
* what happens on rollback or retry.

Do not silently change an existing architectural decision.

---

## Core Invariants

These invariants must remain true unless an approved requirement explicitly changes them:

1. A seat must never be confirmed for more than one user at the same time.
2. A user's active seats for a show must never exceed `per_user_limit`.
3. A successful idempotency key must never create a second reservation.
4. Reusing an idempotency key with a different logical request must return `409 Conflict`.
5. A failed database transaction must not leave partial reservation state.
6. Multi-seat reservations are all-or-nothing.
7. Only the reservation owner may cancel a reservation.
8. Cancellation must not overwrite a newer valid reservation.
9. Expected business conflicts must produce appropriate `4xx` responses, not `5xx`.
10. The reconciliation invariant must hold:

`available + held + confirmed == total_seats`

11. Monetary values must always use integer paise.
12. Persistent correctness must never depend on process-local or in-memory state.

---

## Application Concurrency vs Business Concurrency

Treat these as two different concerns.

### Application-level concurrency

FastAPI is an asynchronous I/O-oriented service.

Use `async`/`await` for I/O-bound application work when the underlying library supports asynchronous operations.

The async model is responsible for allowing many requests to remain in flight efficiently while requests wait for:

* PostgreSQL;
* external HTTP services;
* other I/O operations.

Do not use `asyncio.Lock`, thread locks, or process-local state as the source of truth for seat ownership.

### Business-state concurrency

Concurrency correctness must be enforced by the authoritative persistence layer.

PostgreSQL is the source of truth for:

* seat ownership;
* reservations;
* idempotency state;
* per-user booking state.

Transactions, database constraints, and appropriate row-level locking are the mechanisms used to protect shared business state.

Remember:

> `async` allows requests to execute concurrently; it does not decide which request owns a seat.

Do not confuse efficient request concurrency with correctness of concurrent state changes.

---

## Transaction Boundary

Reservation state changes must occur inside an explicit database transaction.

The transaction must contain all state changes that must succeed or fail together.

Typical reservation state changes include:

```text
idempotency handling
user booking-limit state
seat ownership
reservation record
reservation seat information
reservation status
```

Do not perform unrelated external I/O inside a critical database transaction.

Keep transactions as short as practical while preserving correctness.

If any correctness-critical operation fails before commit, the transaction must roll back without leaving partial state.

---

## Seat Concurrency

Seat allocation is a shared-resource problem.

For every reservation request:

1. Normalize the requested seats.
2. Validate that the requested seats are valid.
3. Establish a deterministic order for locking multiple seats.
4. Acquire the required database locks using the approved database design.
5. Verify the current seat state.
6. Verify the user's booking-limit state.
7. Apply all required state changes within the transaction.
8. Commit only when the complete reservation can succeed.

Never implement:

```text
check seat availability
    ↓
do something else
    ↓
update seat
```

without a mechanism that prevents another transaction from changing the same state between the decision and the update.

A read that observes `AVAILABLE` does not by itself give the caller ownership of the seat.

---

## Multi-Seat Reservations

A request such as:

```text
[A12, A13, A14]
```

is one logical operation.

The current product behavior is:

> **all-or-nothing**

Therefore:

* if all requested seats can be reserved, reserve all of them;
* if any requested seat cannot be reserved, reserve none;
* never leave a partially completed multi-seat reservation.

When locking multiple seats, use one deterministic ordering everywhere.

Do not allow different code paths to acquire the same resources in different orders.

---

## Per-User Booking Limit

The per-user limit is a concurrency invariant, not merely validation.

For a reservation request:

```text
current active seats
+
requested seats
<=
per_user_limit
```

must be evaluated against protected, current state.

Concurrent requests for the same user and show must not independently make decisions using the same stale count.

When implementing or changing this behavior:

1. Identify the authoritative booking-count state.
2. Protect the relevant state using the approved transactional mechanism.
3. Evaluate the limit while that state is protected.
4. Update the state atomically with the reservation.
5. Decrease the same state exactly once when a reservation is cancelled.

Do not solve this with an in-memory counter.

---

## Idempotency

An idempotency key represents one logical reservation operation within its defined scope.

The implementation must support:

### New key

Process the request normally.

### Existing key + same logical request

Return the already committed result without creating another reservation or changing seat ownership again.

### Existing key + different logical request

Return:

```text
409 Conflict
```

and do not execute the new reservation attempt.

### Transaction failure

If the reservation transaction rolls back, its associated idempotency state must roll back as well so a later retry can safely attempt the operation again.

### Commit followed by lost response

If the transaction committed but the client did not receive the response, a retry must resolve to the committed reservation instead of creating another reservation.

Concurrent identical requests must be protected by durable database constraints and transaction semantics. Do not rely only on an application-level existence check.

---

## Cancellation

Cancellation is a state transition, not a delete.

A cancellation must:

1. Authenticate the caller.
2. Verify reservation ownership.
3. Protect the reservation and affected shared state as required.
4. Verify the reservation is currently cancellable.
5. Release the reservation's seats.
6. Update the user's active booking state exactly once.
7. Mark the reservation cancelled.
8. Commit the changes atomically.

Cancellation must not blindly set a seat to `AVAILABLE` if another transaction could legitimately own that seat.

Consider cancellation races explicitly whenever reservation behavior changes.

---

## Deadlocks

If an operation can lock multiple shared rows:

1. Identify all rows that may be locked.
2. Define one deterministic ordering.
3. Use that ordering consistently across all competing code paths.
4. Test multi-resource contention.

Prefer preventing unnecessary deadlocks through consistent ordering rather than relying on accidental execution order.

If deadlock detection or transaction retry is deliberately used, document the behavior and test it.

---

## Failure Scenarios

For every correctness-critical implementation or extension, reason about:

* concurrent requests for the same seat;
* concurrent requests from the same user;
* duplicate requests;
* same key with different request data;
* transaction rollback;
* database connection failure;
* process crash before commit;
* process crash after commit;
* response lost after commit;
* retry after timeout;
* cancellation racing with reservation;
* multiple-seat contention.

Ask:

> Can any valid execution order leave persistent state violating one of the invariants?

If the answer is unclear, the change is not ready.

---

## Future Feature Extensions

Use this skill whenever the service is extended during development or interview exercises.

Before implementing a new feature, classify it.

### New read behavior

Check:

* authorization;
* whether the response exposes authoritative state;
* required indexes;
* whether the feature can reuse existing state without creating duplicate sources of truth.

### New state transition

Check:

* new state;
* valid state transitions;
* affected invariants;
* transaction boundary;
* locking requirements;
* interactions with reserve and cancel;
* rollback behavior.

### New aggregate or stored field

Ask:

* Is this authoritative state or derived state?
* Which domain entity owns it?
* Can it be derived instead of stored?
* Does storing it duplicate an existing fact?
* How will concurrent updates remain consistent?

### New concurrency requirement

Ask:

* What shared resource is contested?
* What is the serialization point?
* What happens when two operations arrive simultaneously?
* What happens when one operation fails?
* What happens when the client retries?
* What happens after process restart?

### New external dependency

Do not add infrastructure automatically.

Before introducing Redis, a message broker, payment service, cache, or another datastore, evaluate:

* why it is required;
* whether PostgreSQL can satisfy the requirement more simply;
* which system becomes authoritative;
* failure behavior;
* consistency implications;
* retry semantics;
* whether the new dependency introduces distributed transaction concerns.

---

## Testing

Correctness-critical changes require automated tests.

Prioritize:

* normal reservation;
* invalid requests;
* seat contention;
* hot-seat concurrency;
* concurrent per-user limit;
* concurrent idempotent requests;
* same-key/different-request rejection;
* transaction rollback;
* cancellation;
* cancellation followed by rebooking;
* reconciliation.

Concurrency correctness should be tested against a real PostgreSQL instance rather than relying only on mocks.

A passing single-request test does not demonstrate concurrency safety.

For any change that affects shared state, include at least one test representing concurrent execution.

---

## Review Checklist

Before considering a reservation change complete, answer:

1. What invariant does this change protect?
2. What is the authoritative state?
3. What is the transaction boundary?
4. What can execute concurrently?
5. What prevents conflicting operations from both succeeding?
6. What happens if the transaction rolls back?
7. What happens if the response is lost after commit?
8. What happens when the same request is retried?
9. Can cancellation race with the operation?
10. Can the change introduce a deadlock?
11. Does reconciliation still hold?
12. Are the important concurrent cases tested?

---

## Engineering Style

Prefer:

* explicit transaction boundaries;
* small and readable service methods;
* database-enforced invariants;
* deterministic behavior;
* focused tests;
* clear domain errors;
* minimal abstractions.

Avoid:

* clever synchronization mechanisms without a concrete requirement;
* duplicated sources of truth;
* hidden transaction boundaries;
* process-local correctness mechanisms;
* broad refactors during feature work;
* speculative architecture;
* unrelated changes;
* swallowing database errors.

Do not introduce multiprocessing, manual threads, background workers, or other concurrency mechanisms merely because the system receives concurrent requests. Introduce them only when there is a demonstrated workload or requirement that benefits from them.

---

## Agent Workflow

For correctness-critical work:

```text
understand
→ identify invariant
→ identify shared state
→ identify transaction boundary
→ reason about concurrency
→ propose approach
→ implement smallest change
→ add/update tests
→ run tests
→ review diff
```

Before implementation, briefly state:

* the invariant being protected;
* the relevant shared state;
* the transaction/concurrency approach;
* the main race condition considered.

After implementation, report:

* what changed;
* what tests were added or updated;
* what concurrent scenarios were tested;
* any remaining assumptions or limitations.

Never claim that code is "race-free" or "concurrency-safe" without explaining the mechanism and providing appropriate test evidence.
