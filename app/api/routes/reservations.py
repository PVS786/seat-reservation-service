from fastapi import APIRouter, Depends, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import ReserveRequest, ReserveResponse
from app.auth import get_current_user_id
from app.services.reservation_service import ReservationService

router = APIRouter(prefix="/shows", tags=["reservations"])

def get_reservation_service(db: AsyncSession = Depends(get_db)) -> ReservationService:
    return ReservationService(db)

@router.post("/{show_id}/reserve", status_code=status.HTTP_201_CREATED, response_model=ReserveResponse)
async def reserve_seats(
    show_id: str,
    request: ReserveRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user_id: str = Depends(get_current_user_id),
    service: ReservationService = Depends(get_reservation_service)
):
    return await service.reserve_seats(show_id, user_id, idempotency_key, request)
