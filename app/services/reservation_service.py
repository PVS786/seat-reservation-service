import hashlib
import json
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.models import Reservation, ReservationSeat
from app.schemas import ReserveRequest, ReserveResponse
from app.repositories.show_repository import ShowRepository
from app.repositories.seat_repository import SeatRepository
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.booking_state_repository import BookingStateRepository

def _generate_request_hash(seats: List[str]) -> str:
    sorted_seats = sorted(seats)
    return hashlib.sha256(json.dumps(sorted_seats, separators=(",", ":")).encode("utf-8")).hexdigest()

class ReservationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.show_repo = ShowRepository(db)
        self.seat_repo = SeatRepository(db)
        self.reservation_repo = ReservationRepository(db)
        self.booking_repo = BookingStateRepository(db)

    async def reserve_seats(self, show_id: str, user_id: str, idempotency_key: str, request: ReserveRequest) -> ReserveResponse:
        if not request.seats:
            raise HTTPException(status_code=400, detail="No seats requested")

        canonical_seats = sorted(request.seats)
        if len(canonical_seats) != len(set(canonical_seats)):
            raise HTTPException(status_code=400, detail="Duplicate seats in request")
            
        req_hash = _generate_request_hash(canonical_seats)
        requested_count = len(canonical_seats)

        try:
            async with self.db.begin():
                show = await self.show_repo.get_by_id(show_id)
                if not show:
                    raise HTTPException(status_code=404, detail="Show not found")

                await self.booking_repo.upsert_booking_state(show_id, user_id)
                booking_state = await self.booking_repo.get_for_update(show_id, user_id)
                
                if not booking_state:
                    raise HTTPException(status_code=500, detail="Could not lock booking state")

                existing_res = await self.reservation_repo.get_by_idempotency_key_for_update(show_id, user_id, idempotency_key)
                
                if existing_res:
                    if existing_res.request_hash == req_hash:
                        res_seats = await self.reservation_repo.get_reservation_seats(str(existing_res.id))
                        return ReserveResponse(
                            reservation_id=existing_res.id,
                            show_id=existing_res.show_id,
                            user_id=existing_res.user_id,
                            seats=sorted(res_seats),
                            amount_paise=existing_res.amount_paise,
                            status=existing_res.status
                        )
                    else:
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key reused with different request")

                seats = await self.seat_repo.get_seats_for_update(show_id, canonical_seats)

                if len(seats) != requested_count:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="One or more requested seats do not exist")

                for seat in seats:
                    if seat.status != 'available':
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Seat {seat.seat_number} is not available")

                if booking_state.active_seat_count + requested_count > show.per_user_limit:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Per-user limit exceeded")

                amount_paise = show.price_paise * requested_count

                new_res = Reservation(
                    show_id=show.id,
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                    request_hash=req_hash,
                    amount_paise=amount_paise,
                    status='confirmed'
                )
                self.reservation_repo.add(new_res)
                await self.db.flush()

                for seat in seats:
                    seat.status = 'confirmed'
                    rs = ReservationSeat(reservation_id=new_res.id, seat_id=seat.id)
                    self.reservation_repo.add_reservation_seat(rs)

                booking_state.active_seat_count += requested_count
                
                response = ReserveResponse(
                    reservation_id=new_res.id,
                    show_id=new_res.show_id,
                    user_id=new_res.user_id,
                    seats=canonical_seats,
                    amount_paise=new_res.amount_paise,
                    status=new_res.status
                )
                
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Database constraint violation")

        return response
