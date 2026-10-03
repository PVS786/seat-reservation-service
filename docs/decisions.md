# Architectural and Design Decisions

This document records the critical architectural and design decisions made for the seat reservation service.

## 1. Multi-Seat Booking Semantics
**Decision:** All-or-Nothing (Strict Failure).
**Rationale:** If a user requests multiple seats (e.g., `["A12", "A13"]`), the entire request will fail if any single requested seat is unavailable. This provides a predictable API contract without unexpected partial confirmations, aligning with typical user expectations that they want to attend an event together or not at all.

## 2. Release Model
**Decision:** Explicit Cancellation.
**Rationale:** We will implement an explicit `POST /reservations/{id}/cancel` endpoint. We will not implement auto-expiring time-boxed holds for this iteration. Only the owner of the reservation (derived strictly from the auth token) can execute this cancellation, cleanly returning the seats to the `available` state.

## 3. Idempotency Key Transport
**Decision:** HTTP Header.
**Rationale:** The idempotency key will be passed via a custom HTTP header (e.g., `Idempotency-Key: <UUID>`). This separates control metadata from the business payload, keeping the JSON body focused purely on domain data and aligning with standard HTTP idempotency practices.

## 4. Authentication Mechanism
**Decision:** Signed JWT Bearer Tokens.
**Rationale:** User identity will be derived securely from a signed JWT Bearer token passed in the `Authorization: Bearer <token>` header. While we won't integrate a real Identity Provider (IdP) to keep the scope focused, the service will cryptographically verify the JWT signature to trust the embedded `user_id`. This allows stateless authentication without an extra database lookup per request.

## 5. Deployment Platform
**Decision:** Render.
**Rationale:** The final deployment will target Render's free tier. However, the immediate engineering focus will be entirely on local development, Docker containerization, and local concurrency/burst testing until the correctness bar is fully met.

## 6. Datastore Atomic Strategy (Pending)
**Decision:** (To Be Decided during Schema Design)
**Rationale:** While we know we are using PostgreSQL, we still need to formalize the exact race-free mechanism (e.g., `SELECT FOR UPDATE` vs. Unique Constraints vs. explicit Lock Ordering). This will be defined in the architecture and schema design phase.
