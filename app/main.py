from fastapi import FastAPI
from app.api.routes import shows, reservations, metrics, health
from app.logging_config import setup_logging
from app.middleware.logging import LoggingMiddleware

setup_logging()

app = FastAPI(title="Seat Reservation Service")

app.add_middleware(LoggingMiddleware)

app.include_router(health.router)
app.include_router(shows.router)
app.include_router(reservations.router)
app.include_router(metrics.router)
