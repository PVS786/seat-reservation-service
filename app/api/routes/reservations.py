from fastapi import APIRouter, Depends, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import ReserveRequest, ReserveResponse, CancelResponse
from app.auth import get_current_user_id
from app.services.reservation_service import ReservationService

router = APIRouter(tags=["reservations"])

def get_reservation_service(db: AsyncSession = Depends(get_db)) -> ReservationService:
    return ReservationService(db)

@router.post("/shows/{show_id}/reserve", status_code=status.HTTP_201_CREATED, response_model=ReserveResponse)
async def reserve_seats(
    show_id: str,
    request: ReserveRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user_id: str = Depends(get_current_user_id),
    service: ReservationService = Depends(get_reservation_service)
):
    return await service.reserve_seats(show_id, user_id, idempotency_key, request)

@router.post("/reservations/{reservation_id}/cancel", status_code=status.HTTP_200_OK, response_model=CancelResponse)
async def cancel_reservation(
    reservation_id: str,
    user_id: str = Depends(get_current_user_id),
    service: ReservationService = Depends(get_reservation_service)
):
    return await service.cancel_reservation(reservation_id, user_id)
