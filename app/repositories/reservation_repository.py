
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models import Reservation, ReservationSeat, Seat


class ReservationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_idempotency_key_for_update(
        self, show_id: str, user_id: str, idempotency_key: str
    ) -> Reservation | None:
        return (
            await self.db.execute(
                select(Reservation)
                .where(
                    Reservation.show_id == show_id,
                    Reservation.user_id == user_id,
                    Reservation.idempotency_key == idempotency_key,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def get_by_id_for_update(self, reservation_id: str) -> Reservation | None:
        return (
            await self.db.execute(
                select(Reservation)
                .where(Reservation.id == reservation_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def get_by_id(self, reservation_id: str) -> Reservation | None:
        return (
            await self.db.execute(
                select(Reservation).where(Reservation.id == reservation_id)
            )
        ).scalar_one_or_none()

    async def get_reservation_seats(self, reservation_id: str) -> list[str]:
        return list(
            (
                await self.db.execute(
                    select(Seat.seat_number)
                    .join(ReservationSeat, Seat.id == ReservationSeat.seat_id)
                    .where(ReservationSeat.reservation_id == reservation_id)
                )
            )
            .scalars()
            .all()
        )

    def add(self, reservation: Reservation):
        self.db.add(reservation)

    def add_reservation_seat(self, reservation_seat: ReservationSeat):
        self.db.add(reservation_seat)
