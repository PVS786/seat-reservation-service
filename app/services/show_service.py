from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Seat, Show
from app.repositories.seat_repository import SeatRepository
from app.repositories.show_repository import ShowRepository
from app.schemas import SeatResponse, ShowCreate, ShowDetailResponse


class ShowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.show_repo = ShowRepository(db)
        self.seat_repo = SeatRepository(db)

    async def create_show(self, show_in: ShowCreate) -> Show:
        if not show_in.seats:
            raise HTTPException(
                status_code=400, detail="Must provide at least one seat"
            )

        if len(show_in.seats) != len(set(show_in.seats)):
            raise HTTPException(status_code=400, detail="Duplicate seats in request")

        new_show = Show(
            name=show_in.name,
            price_paise=show_in.price_paise,
            total_seats=len(show_in.seats),
        )

        try:
            async with self.db.begin():
                self.show_repo.add(new_show)
                await self.db.flush()

                for seat_num in show_in.seats:
                    new_seat = Seat(show_id=new_show.id, seat_number=seat_num)
                    self.seat_repo.add(new_seat)
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Database constraint violation")
        except HTTPException:
            raise

        return new_show

    async def get_show_detail(self, show_id: str) -> ShowDetailResponse:
        show = await self.show_repo.get_by_id(show_id)
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")

        seats = await self.seat_repo.get_seats_by_show_id_ordered(show_id)

        available = 0
        confirmed = 0
        seat_responses = []
        for seat in seats:
            if seat.status == "available":
                available += 1
            elif seat.status == "confirmed":
                confirmed += 1
            seat_responses.append(
                SeatResponse(seat_number=seat.seat_number, status=seat.status)
            )

        return ShowDetailResponse(
            id=show.id,
            name=show.name,
            price_paise=show.price_paise,
            per_user_limit=show.per_user_limit,
            total_seats=show.total_seats,
            seats=seat_responses,
            available=available,
            held=0,
            confirmed=confirmed,
        )
