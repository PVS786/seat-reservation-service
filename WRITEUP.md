# Seat Reservation Service - Write-up

## 1. Atomic decision

The main correctness problem in this assignment is making sure that two concurrent requests cannot confirm the same seat.

I handle this in PostgreSQL using a database transaction and `SELECT ... FOR UPDATE` on the requested seat rows.

For a reservation request, I first start one transaction. The requested seats are sorted into a fixed order and the corresponding seat rows are locked. I then check that every requested seat is still `available`. If they are, I create the reservation, change the seats to `confirmed`, update the user's active seat count, and commit everything in the same transaction.

For example, if 100 users request `A1` at the same time, only one transaction can hold the `A1` row lock first. That transaction sees `available`, changes it to `confirmed`, and commits. The other transactions wait for the lock and then see the committed `confirmed` state, so they return `409 Conflict`.

So the requests themselves can run concurrently, but the conflicting decision about the same database row is serialized by PostgreSQL. There is no application-level lock or in-memory seat state involved.

The per-user booking limit is protected in a similar way. I keep a `user_show_booking_state` row for each `(show_id, user_id)` pair and lock that row before checking/updating `active_seat_count`. This prevents several concurrent requests from all reading the same old count and collectively exceeding the limit.

### Multi-seat and deadlock avoidance

For multi-seat reservations, I sort the requested seats before locking them. This means all transactions use the same lock order.

For example, `["A2", "A1"]` becomes `["A1", "A2"]`.

This avoids the classic case where one transaction locks `A1` and waits for `A2` while another locks `A2` and waits for `A1`. With a deterministic order, overlapping transactions wait in the same direction instead of creating a circular wait.

## 2. Idempotency

The idempotency key is stored directly on the `reservations` table together with the authenticated `user_id`, `show_id`, and a hash of the requested seat list.

The database has a unique constraint on:

`(show_id, user_id, idempotency_key)`

The logical idempotency scope is therefore the show, authenticated user, and idempotency key.

There are three cases:

- A new key: process the reservation normally.
- Same key and same request: return the existing reservation instead of creating another one.
- Same key and a different request: return `409 Conflict`.

The request hash is calculated from the canonical sorted seat list. This also means that requests such as `["A1", "A2"]` and `["A2", "A1"]` are treated as the same request.

The user/show booking-state row is locked before checking the idempotency record. This is important for concurrent duplicate requests because the first request can create the reservation while the other requests are waiting. Once they continue, they find the already committed reservation and replay it.

I consider exactly-once here to mean that one successful logical operation results in one committed reservation. The same request may be sent multiple times over HTTP, but it does not create multiple reservations.

If a transaction fails before commit, the reservation and its idempotency state are rolled back as well, so a later retry can try the operation again.

## 3. Holds and expiry

I did not implement time-based holds in this version.

I chose explicit cancellation option as given in the requirements instead because it keeps the state model simple.

A seat is either `available` or `confirmed` internally. When a confirmed reservation is cancelled, the cancellation transaction releases its seats back to `available` and decrements the user's active seat count.

## 4. Consistency vs availability

PostgreSQL is the source of truth for seats, reservations, idempotency state, and booking limits.

Because of that, reservation writes depend on the database being reachable. If the application cannot reach PostgreSQL, I would rather fail the reservation than accept it using stale or local state.

This means the system favors consistency over availability for reservation decisions during a database partition.

For example, if the database is unavailable, the service cannot safely decide whether `A1` is still available, so it should not continue accepting bookings based on an in-memory assumption.

This was a deliberate choice because selling the same seat twice is a much worse outcome than temporarily rejecting a reservation.

## 5. Observability

The service exposes health endpoints, Prometheus-compatible metrics, and structured logs with a request/correlation ID.

At 2am, I would want to be alerted for things that indicate a system problem, such as:

- PostgreSQL unavailable or readiness continuously failing
- unexpected `5xx` responses
- application crashes or restart loops
- an inconsistency between reported seat state and the reconciliation invariant

The burst test also checks the API response distribution, metrics changes, and final seat reconciliation.

## 6. AI usage

I used AI tools as development assistants during the project. They were used for things such as generating initial boilerplate, suggesting implementation approaches, helping with tests, reviewing concurrency edge cases, debugging issues, linting, and documentation purpose.

The main architecture and correctness decisions were still directed and reviewed by me. In particular, I decided on PostgreSQL as the source of truth, the transaction boundaries, row-locking strategy, deterministic seat-lock ordering, per-user booking-state locking, idempotency behavior, and explicit cancellation.

I reviewed the AI-assisted code and validated it locally through tests and concurrency scenarios.

## 7. What I would do next

I would first make the current system more production-ready by improving authentication, testing it under higher load, and adding better monitoring.

Later, if the product needs seat holds, I would add a simple expiry mechanism.