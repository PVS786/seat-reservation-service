
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models import Seat


class SeatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def add(self, seat: Seat):
        self.db.add(seat)

    async def get_seats_for_update(
        self, show_id: str, seat_numbers: list[str]
    ) -> list[Seat]:
        return list(
            (
                await self.db.execute(
                    select(Seat)
                    .where(Seat.show_id == show_id, Seat.seat_number.in_(seat_numbers))
                    .order_by(Seat.seat_number)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

    async def get_seats_by_show_id_ordered(self, show_id: str) -> list[Seat]:
        return list(
            (
                await self.db.execute(
                    select(Seat)
                    .where(Seat.show_id == show_id)
                    .order_by(Seat.seat_number)
                )
            )
            .scalars()
            .all()
        )

    async def get_available_seat_counts(self) -> dict:
        result = await self.db.execute(
            select(Seat.show_id, func.count(Seat.id))
            .where(Seat.status == "available")
            .group_by(Seat.show_id)
        )
        return {str(row[0]): row[1] for row in result.all()}
