from fastapi import APIRouter, Depends, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repositories.seat_repository import SeatRepository
from app.metrics import registry, seats_available

router = APIRouter(tags=["metrics"])

@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    seat_repo = SeatRepository(db)
    available_counts = await seat_repo.get_available_seat_counts()
    
    seats_available.clear()
    for show_id, count in available_counts.items():
        seats_available.labels(show_id=str(show_id)).set(count)
        
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
