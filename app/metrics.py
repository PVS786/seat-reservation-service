from prometheus_client import CollectorRegistry, Counter, Gauge

registry = CollectorRegistry()

reservations_confirmed_total = Counter(
    "reservations_confirmed_total",
    "Number of NEW reservations successfully committed",
    registry=registry,
)

reservations_declined_total = Counter(
    "reservations_declined_total",
    "Number of reservations declined",
    ["reason"],
    registry=registry,
)

idempotent_replays_total = Counter(
    "idempotent_replays_total",
    "Number of requests that replayed an existing successful reservation",
    registry=registry,
)

seats_available = Gauge(
    "seats_available",
    "Current number of seats available",
    ["show_id"],
    registry=registry,
)
