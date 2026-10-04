from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models import UserShowBookingState


class BookingStateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_booking_state(self, show_id: str, user_id: str):
        stmt = (
            insert(UserShowBookingState)
            .values(show_id=show_id, user_id=user_id, active_seat_count=0)
            .on_conflict_do_nothing()
        )
        await self.db.execute(stmt)

    async def get_for_update(
        self, show_id: str, user_id: str
    ) -> UserShowBookingState | None:
        return (
            await self.db.execute(
                select(UserShowBookingState)
                .where(
                    UserShowBookingState.show_id == show_id,
                    UserShowBookingState.user_id == user_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
