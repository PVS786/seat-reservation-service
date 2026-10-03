from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.models import Seat

class SeatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def add(self, seat: Seat):
        self.db.add(seat)

    async def get_seats_for_update(self, show_id: str, seat_numbers: List[str]) -> List[Seat]:
        return list((await self.db.execute(
            select(Seat)
            .where(Seat.show_id == show_id, Seat.seat_number.in_(seat_numbers))
            .order_by(Seat.seat_number)
            .with_for_update()
        )).scalars().all())
