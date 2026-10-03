from fastapi import FastAPI
from app.api.routes import shows, reservations

app = FastAPI(title="Seat Reservation Service")

app.include_router(shows.router)
app.include_router(reservations.router)
