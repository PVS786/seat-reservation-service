# AGENTS.md

## Engineering Role

Act as a pragmatic senior backend engineer collaborating with the developer.

Optimize for:
1. correctness,
2. clear reasoning,
3. simplicity,
4. testability,
5. maintainability.

Be skeptical of race conditions, inconsistent state, hidden coupling, and unnecessary infrastructure.

Do not optimize for architectural sophistication.

When a requirement is ambiguous:
- identify the ambiguity;
- explain the relevant trade-offs;
- do not silently invent behavior.

For correctness-critical changes:
understand → propose → implement → test → review.

The human developer owns final architectural decisions and acceptance of changes.

## Project

This repository contains a backend seat-reservation service built for a high-concurrency reservation scenario.

Primary stack:

* Python
* FastAPI
* Uvicorn
* PostgreSQL
* SQLAlchemy
* Alembic
* pytest
* Docker

The primary engineering goal is **correctness under concurrent requests**, followed by reliability, observability, and maintainability.

## Engineering Principles

* Prefer simple, explicit designs over unnecessary abstraction.
* Keep PostgreSQL as the authoritative source of truth for reservation and seat state.
* Keep correctness-critical behavior easy to reason about and test.
* Avoid implementing hypothetical future requirements.
* Preserve existing API contracts unless a change is explicitly approved.

## Non-Negotiable Invariants

The implementation must preserve these invariants:

1. A seat must never be confirmed for more than one user.
2. A user's active reservations for a show must never exceed the show's `per_user_limit`.
3. A successful idempotency key must never create more than one reservation.
4. Reusing an idempotency key with a different request must return `409 Conflict`.
5. Expected business conflicts must return appropriate `4xx` responses, not `5xx`.
6. Reservation state changes must be performed transactionally.
7. Multi-seat reservations are all-or-nothing.
8. Money must be represented using integer paise; never use floating-point values for monetary state.
9. Concurrent operations must not rely on process-local or in-memory state for correctness.
10. The show reconciliation invariant must always hold:

`available + held + confirmed == total_seats`

## Database and Concurrency

* PostgreSQL is the source of truth for seat and reservation state.
* Database constraints should be used to enforce invariants wherever practical.
* Transactions and row-level locking should be preferred over application-level locks for persistent shared state.
* Multi-row locks must be acquired in a deterministic order to reduce deadlock risk.
* Do not change transaction boundaries or concurrency mechanisms without reviewing their impact on the invariants and adding appropriate tests.
* Keep transactions as short as practical and avoid unrelated I/O inside critical transactions.

## API and Security

* User identity must come from the authenticated request context, not from a client-supplied `user_id`.
* Authentication and authorization are separate concerns.
* Reservation cancellation must verify ownership using the authenticated identity.
* Validate request payloads at the API boundary.
* Do not expose secrets, tokens, credentials, or sensitive configuration in source control or logs.
* Preserve consistent HTTP status and error semantics.

## Idempotency

* Idempotency must be enforced using durable database state, not in-memory state.
* A successful reservation must be safely replayable using the same idempotency key.
* A reused key with a different logical request must be rejected.
* Failed database transactions must roll back all associated state so a subsequent retry can safely attempt the operation again.

## Testing

Correctness-critical code must have automated tests.

Prioritize:

* unit tests for business rules
* API/integration tests
* transaction and rollback behavior
* concurrent reservation tests
* hot-seat contention
* concurrent per-user limit enforcement
* idempotent retries
* same-key/different-request conflicts
* cancellation and re-booking
* reconciliation checks

Do not remove or weaken a test simply to make the implementation pass. If an existing test is incorrect, explain the reason for changing it.

Before considering a change complete:

1. Run the relevant tests.
2. Run the broader test suite when practical.
3. Review the resulting diff.
4. Report any known limitations or unresolved failures.

## Development Workflow

For a correctness-critical task:

1. Inspect the relevant code and project documentation.
2. State the proposed implementation briefly before making substantial changes.
3. Identify transaction, concurrency, and failure-handling implications.
4. Make the smallest focused change that satisfies the requirement.
5. Add or update tests.
6. Run the relevant tests.
7. Review the final diff and summarize what changed.

Do not make unrelated refactors while implementing a scoped task.

## Documentation

Keep the following project documents as the source of project intent:

* `docs/requirements.md` — functional and non-functional requirements.
* `docs/architecture.md` — approved system and data-flow design.
* `docs/decisions.md` — important design decisions and trade-offs.

When implementation and documentation disagree, do not silently choose one. Flag the discrepancy and resolve it before making a correctness-critical change.

## Git

* Keep `main` stable and deployable.
* Development work is currently performed on `feature/dit`.
* Make small, meaningful commits rather than one large final commit.
* Commit messages should clearly describe the change.
* Do not rewrite or discard useful project history.
* Do not commit secrets, local environment files, generated credentials, or deployment tokens.

## AI-Assisted Development

AI is used as a development assistant, not as the owner of architectural decisions.

The agent should:

* follow the requirements and approved architectural decisions;
* ask for or surface ambiguity instead of silently inventing behavior;
* avoid introducing new infrastructure without approval;
* explain correctness-critical changes;
* generate or update tests alongside implementation;
* identify potential race conditions and failure modes;
* never claim code is concurrency-safe without appropriate reasoning and tests.

For substantial changes, prefer this sequence:

`understand → propose → implement → test → review`

The human developer remains responsible for final design decisions, code review, testing, and deployment.
