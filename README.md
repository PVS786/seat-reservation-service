# Seat Reservation Service

## Overview

This is a backend seat reservation service built to handle concurrent reservation requests safely.

PostgreSQL is the source of truth for seats, reservations, idempotency, and per-user booking state.

The main things the service protects are:
- A seat cannot be confirmed for two users at the same time.
- A user cannot exceed the per-show booking limit.
- Retrying the same request does not create another reservation.
- Reusing an idempotency key for a different request returns `409 Conflict`.
- Multi-seat reservations succeed or fail as one operation.
- Reservations can be cancelled explicitly.

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn
- SQLAlchemy (async)
- PostgreSQL
- Alembic
- Docker / Docker Compose
- Prometheus-compatible metrics

## Repository Structure

```text
seat-reservation-service/
├── alembic/                # Database migration scripts
├── app/                    # FastAPI application code (routes, services, models)
├── tests/                  # Automated pytest suite
├── .env.example            # Example environment configuration
├── alembic.ini             # Alembic configuration
├── burst.py                # Concurrent stress-testing script
├── docker-compose.yml      # Local Docker multi-container setup
├── Dockerfile              # Instructions to build the application container
├── README.md               # Setup and documentation (this file)
├── requirements.txt        # Python dependencies
└── WRITEUP.md              # Assessment design decisions and write-up
```

## Running Locally

This project is tested on Windows but can run in any standard Python environment. You will need Python 3.10+ and a local instance of PostgreSQL running.

1. **Clone the repository**
   ```bash
   git clone <repository_url>
   cd seat-reservation-service
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and ensure `DATABASE_URL` points to your local PostgreSQL instance (e.g., `postgresql+asyncpg://postgres:postgres@localhost:5432/seat_reservation`). Set a secret for `JWT_SECRET` and match it in `BURST_JWT_SECRET` if you plan to run tests locally.

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start FastAPI**
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
   ```

7. **Verify the service**
   The application is running locally. You can check:
   - Interactive docs: http://127.0.0.1:8001/docs
   - Liveness: http://127.0.0.1:8001/health/live
   - Readiness: http://127.0.0.1:8001/health/ready
   - Metrics: http://127.0.0.1:8001/metrics

## Running with Docker

The easiest way to run the entire stack (FastAPI app and PostgreSQL) is using Docker Compose.

The setup consists of two containers:
- `app`: Built from the `Dockerfile`, runs the FastAPI service.
- `db`: A PostgreSQL 15 alpine image.

1. **Start the containers**
   ```bash
   docker compose up --build
   ```

The `app` container is configured to automatically run `alembic upgrade head` before starting the server.

The application port `8000` inside the container is mapped to port `8001` on your local host. You can access the API at `http://127.0.0.1:8001`.

2. **Stop the containers**
   ```bash
   docker compose down
   ```

3. **Wipe database data**
   PostgreSQL data is stored in a persistent Docker volume named `postgres_data`. To remove the containers **and** permanently wipe the database data, use the `-v` flag:
   ```bash
   docker compose down -v
   ```

## Environment Variables

Local application configuration is handled via `.env`, which is ignored by Git. `.env.example` contains safe placeholders. Do not commit actual secrets to source control.

| Variable | Used by | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | app | SQLAlchemy database connection string |
| `JWT_SECRET` | app | Signing and validating application JWTs |
| `LOG_LEVEL` | app | Python logging level (defaults to `DEBUG`) |
| `BURST_JWT_SECRET` | burst.py | Local secret used by the script to sign valid test JWTs |
| `BASE_URL` | burst.py | Default target URL for the burst test script |

## Database Migrations

This project uses Alembic to manage database schema changes. The SQLAlchemy models define the schema, and migrations track changes over time in `alembic/versions`.

- To apply pending migrations manually, run: `alembic upgrade head`.
- The provided Docker setup automatically applies pending migrations before starting the application.

## API Documentation

FastAPI generates interactive OpenAPI documentation automatically.

- **Local:** http://127.0.0.1:8001/docs
- **Deployed:** https://seat-reservation-service-iuz0.onrender.com/docs
- **OpenAPI Schema:** `/openapi.json`

The `/docs` endpoint acts as the API contract. It lists request bodies, response codes, headers, and schemas for every available endpoint.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/shows` | Create a new show with a specific capacity and seat map |
| POST   | `/shows/{show_id}/reserve` | Book one or more seats for a show using an idempotency key |
| POST   | `/reservations/{reservation_id}/cancel` | Cancel an existing confirmed reservation |
| GET    | `/shows/{show_id}` | Fetch a show's current seat state and available/confirmed counts |
| GET    | `/health/live` | Checks if the application process is running |
| GET    | `/health/ready` | Checks if the application can reach PostgreSQL |
| GET    | `/metrics` | Exposes Prometheus-compatible application metrics |

## Burst Testing

The repository includes `burst.py`, a simple, targeted concurrent load-testing tool designed to test the application's main concurrency and idempotency cases. It uses Python's `requests` library and a `ThreadPoolExecutor` to send concurrent requests to the application.

### Burst Test Configuration

You can find the CLI options by running:
```bash
python burst.py --help
```

Arguments:
- `--base-url`: The URL of the target service.
- `--scenario`: The specific correctness scenario to run.
- `--requests`: The total number of reservation requests generated. Defaults to `100`.
- `--concurrency`: The maximum number of parallel HTTP requests the script can send. Defaults to `50`.

*Note:* `requests` defines how many total attempts are made, while `concurrency` defines the maximum number of requests the script allows to be in flight at the same time.

### Scenario 1 - Hot Seat

This scenario proves that the service prevents double-booking.
- Creates a fresh show with exactly 1 physical seat.
- Fires highly concurrent requests from different users targeting the exact same seat.
- **Expected Outcome:** Exactly one request succeeds (`201`), all others are safely rejected (`409`), the final confirmed seat count is `1`, and the `seat-unavailable` metric reflects the declines.

### Scenario 2 - Per-user Limit

This scenario proves that a single user cannot bypass the booking limits by firing simultaneous requests.
- Creates a show with plenty of seats.
- A single authenticated user fires requests for many different distinct seats concurrently.
- **Expected Outcome:** The system enforces the per-user limit. At most 4 requests succeed because the default per-user limit is 4. With the default 100-request test, the expected result is 4 successful requests and the remaining requests returning `409`, and the `per-user-limit` metric accurately reflects the rejections.

### Scenario 3 - Idempotency

This scenario proves that identical concurrent retries do not create duplicate records.
- Creates a show and fires the identical request body using the identical idempotency key concurrently.
- **Expected Outcome:** All requests succeed (`201`), but only **one unique reservation ID** is ever generated. The underlying database state is modified exactly once, and subsequent responses are safely replayed.

### Scenario 4 - Same Key, Different Request

This scenario proves that reusing an idempotency key for a logically distinct request is prevented.
- Generates concurrent requests using the exact same idempotency key but entirely different requested seats.
- **Expected Outcome:** One request creates a reservation. All subsequent conflicting requests are rejected with `409 Conflict`.

### Scenario 5 - Multi-seat

This scenario checks concurrent multi-seat reservations and the deterministic lock ordering used to avoid deadlocks caused by conflicting seat lock order.
- Fires highly concurrent requests from different users. Each request attempts to book exactly 3 randomized overlapping seats out of a 20-seat show.
- **Expected Outcome:** The API correctly acquires multi-row locks in deterministic order. Every successful response confirms exactly 3 seats without overlapping ownership.

### Scenario 6 - Health

Checks the `/health/live` and `/health/ready` endpoints to confirm standard 200 operational status.

### Understanding Burst Output

The script strictly parses and separates HTTP outcomes and Prometheus metric changes.

- **HTTP RESULTS:** The raw API response distribution (e.g. `201`, `409`). Shows whether the application responded cleanly without unexpected `5xx` errors.
- **METRICS:** Parses the actual `/metrics` endpoint before and after the burst, calculating the exact delta.
  - *New reservations confirmed:* Requests resulting in new committed reservations.
  - *Reservations declined - seat unavailable:* Requests rejected because one or more requested seats were already unavailable. This is a count of declined requests, not physical seats.
  - *Idempotent replays:* Duplicate requests that were successfully identified and safely replayed.
- **RECONCILIATION:** Validates the fundamental system invariant: `available + held + confirmed == total_seats`.

### How to run burst locally

Ensure your application is running (e.g. via Docker Compose on port 8001). Configure `BURST_JWT_SECRET` in your `.env` to match the `JWT_SECRET` used by the application, so the script can generate valid test tokens.

```bash
python burst.py --base-url http://127.0.0.1:8001 --scenario hot-seat --requests 20 --concurrency 10
```

*Note: Run `burst.py` from your host terminal, not from inside the Docker container.*

## Live Deployment

The API is deployed and accessible at:
**https://seat-reservation-service-iuz0.onrender.com**

You can run the burst test against this live URL directly from your local machine. You only need the Python dependencies installed locally, and you must set `BURST_JWT_SECRET` to the actual production secret used on Render. 

**The burst script runs from your local machine. It does not need to be deployed to Render. It sends HTTP requests to the live Render service.**

```text
Your laptop
    |
    | HTTPS
    v
Render FastAPI
    |
    v
Render PostgreSQL
```

```bash
python burst.py --base-url https://seat-reservation-service-iuz0.onrender.com --scenario hot-seat --requests 50 --concurrency 25
```

## Metrics and Logs

- **Live Metrics:** https://seat-reservation-service-iuz0.onrender.com/metrics
- **Live Logs:** Standard structured application logs with correlation IDs are available in the Render dashboard's Logs view.
- **Local Logs:** If running locally, you can view the structured JSON logs in your terminal or via `docker compose logs app`.

## Tests

The project includes an automated test suite enforcing application correctness and isolating database states per test. Run it via:

```bash
pytest
```

To run the linter:

```bash
ruff check .
```
