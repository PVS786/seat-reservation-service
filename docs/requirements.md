# Engineering Specification: Seat Reservation Service

## 1. Scope
Build, deploy, and operate a small backend service that sells assigned seats for an event (e.g., concert or movie hall) and allows users to reserve them. The primary engineering goal is to maintain absolute correctness under high concurrency load (e.g., tens of thousands of buyers hitting "book" within the same second), ensuring no double-selling, enforcement of user booking limits, and exactly-once processing of retried requests.

## 2. Functional Requirements
* **Create a Show:** Support creation of a show with a specified number of seats and a fixed price.
* **Reserve Seat(s):** Allow authenticated users to reserve one or more seats using an idempotency key.
* **Release/Cancel Seat(s):** Support releasing a held or confirmed seat to make it available again.
* **Show State:** Provide an endpoint to retrieve the current state of a show, including individual seat statuses and aggregated counts.

## 3. API Contracts
The service must expose a JSON HTTP API. Monetary values must be represented strictly as integer minor units (paise); never use floating-point types.

**3.1. Create a Show (Admin)**
* **Endpoint:** `POST /shows`
* **Request Payload Example:**
  ```json
  { "name": "friday-night", "seats": ["A1","A2","A3"], "price_paise": 25000 }
  ```
* **Response:** Returns the created show with a unique ID and every requested seat initialized in the "available" state.

**3.2. Reserve a Seat (Authenticated User)**
* **Endpoint:** `POST /shows/{id}/reserve`
* **Request Payload Example:**
  ```json
  { "seats": ["A12"], "idempotency_key": "..." }
  ```
  *(Note: The assignment permits `idempotency_key` to be passed in the header or body).*
* **Success Response (201 Created):**
  ```json
  {
    "reservation_id": "...",
    "show_id": "...",
    "user_id": "...",
    "seats": ["A12"],
    "amount_paise": 25000,
    "status": "confirmed"
  }
  ```

**3.3. Release/Expire a Hold**
* **Endpoint:** `POST /reservations/{id}/cancel` (if using explicit cancellation) OR behavior governing time-boxed expiration.
* **Requirement:** A released seat must cleanly return to an available, re-bookable state. A release must never resurrect a seat that is already confirmed to another user.

**3.4. Show State**
* **Endpoint:** `GET /shows/{id}`
* **Response:** Must return per-seat status (available / held / confirmed) and aggregate counts.

## 4. Authentication and Authorization Requirements
* User identity must be strictly derived from the authenticated request token, never from an arbitrary user-supplied field in the request body.
* If a request attempts to spoof a body field acting "as" another user, the operation must still only act as the token's legitimate owner.
* A user can only cancel their own reservations/holds.

## 5. Reservation Correctness Requirements
* **Concurrency Scale:** The service must survive and correctly handle a storm of ~20,000 concurrent reservation requests against a fresh show, particularly with high contention for a few "hot" seats.
* **No Double-Sell:** A seat confirmed or actively held for one user can never be confirmed for another. In a race for a single seat, exactly one request yields a `201 Created`; all losers must receive a clean `409 Conflict` decline.
* **Zero 5xx on Business Declines:** Expected domain failures (seat taken, limit exceeded, idempotent conflict) must return `4xx` (specifically `409` where applicable), never a `5xx` server error.
* **Per-User Limit:** A user cannot hold more than `per_user_limit` seats for a single show. The default limit is `4`. If a user attempts to exceed this limit (e.g., firing 10 parallel reservation requests), they must successfully acquire at most 4 seats, with the rest receiving clean `4xx` declines.

## 6. Idempotency Requirements
* The same idempotency key must reserve exactly once. A retry with the identical key and identical request body must return the original reservation outcome.
* The same idempotency key supplied with a different request body (e.g., asking for different seats) must be rejected with a `409 Conflict`.
* Idempotent retries must not result in any extra side effects or state changes.

## 7. Multi-Seat Behavior
* The assignment leaves the exact behavior of multi-seat requests (e.g., requesting `["A12", "A13"]` when only one is available) open to our design choice. We must decide whether this is an all-or-nothing transaction or a best-effort allocation. Whatever is chosen must be explicitly documented and enforced safely under concurrency.

## 8. Cancellation/Release Behavior
* The assignment explicitly allows two models:
  1. An explicit `POST /reservations/{id}/cancel` endpoint (owner-only).
  2. A time-boxed hold that auto-expires and returns the seat to available.
* We must choose one model (or a combination) and ensure correctness.

## 9. Show-State and Reconciliation Requirements
* The reconciliation invariant must hold to the exact unit at all times, including during and after intense burst traffic.
* **Invariant:** `available + held + confirmed == total_seats`

## 10. Health/Readiness Requirements
* **Liveness Endpoint:** A basic endpoint indicating the application process is running.
* **Readiness Endpoint:** Must actively verify dependency health (e.g., the database is reachable). It must fail closed (return unhealthy) when dependencies are down.

## 11. Metrics and Logging Requirements
* **Metrics:** Expose a Prometheus-style endpoint `/metrics`. At a minimum, it must track:
  * Reservations confirmed (counter)
  * Reservations declined by reason (counter: seat-taken, per-user-limit, idempotent-replay)
  * Seats available (gauge)
* Metrics must accurately reconcile with the datastore API state and observed burst results.
* **Logs:** Implement structured logging (e.g., JSON). Every log line must include a correlation/request ID to trace individual requests across the stack.

## 12. Deployment Requirements
* The service must be fully containerized via `Dockerfile` (or `docker-compose.yml`) ensuring a clean checkout runs identically to production.
* The service must be deployed to a public, accessible URL (e.g., Render, Railway, Fly.io).
* The service must survive a cold start and correctly surface healthy statuses once ready.

## 13. Burst/Load-Testing Requirements
* Deliver a one-command burst script (e.g., `make burst`, `./burst.sh <BASE_URL>`, or a small program).
* The script must reproduce the on-sale stampede against the live URL, including a hot-seat storm (many users fighting for the same seat).
* The script must output the outcome distribution (`201` confirmed, `4xx` declined-by-reason, `5xx` errors) and display the final reconciliation state.

## 14. Deliverables
1. Public Git repo with full, incremental commit history.
2. Live URL of the deployed service.
3. The one-command burst script, documented in the `README.md`.
4. Access to live metrics and logs (or a short screen recording if the platform limits public access).
5. A `WRITEUP.md` document explaining the atomic decision mechanism, idempotency strategy, holds & expiry strategy, consistency vs. availability under partitions, observability considerations, AI usage, and future next steps.

## 15. Open Decisions (Explicit Choices to be Made)
The following are choices explicitly left to the developer by the assignment, which must be decided and documented prior to or during implementation:

1. **Multi-Seat Booking Semantics:** If a user requests multiple seats but only a subset are available, should the system fail the entire request (all-or-nothing) or book the available subset (best-effort)?
2. **Release Model:** Will we use explicit cancellation (`POST /reservations/{id}/cancel`), time-boxed automatic holds, or both?
3. **Idempotency Key Transport:** Should the `idempotency_key` be passed in the HTTP headers or within the JSON body?
4. **Authentication Flow Implementation:** How will the auth token be passed (e.g., Bearer token) and validated (e.g., JWT vs. opaque token lookup) since identity must derive entirely from the token?
5. **Datastore atomic strategy:** We must finalize the exact atomic concurrency control mechanism (e.g., `SELECT FOR UPDATE`, unique constraints, deterministic lock ordering) that we will use in PostgreSQL.
6. **Deployment Platform:** Which free-tier public provider (Render, Railway, Fly.io) will be used for the live URL?
