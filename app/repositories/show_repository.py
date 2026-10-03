from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import Show

class ShowRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, show_id: str) -> Show | None:
        return (await self.db.execute(select(Show).where(Show.id == show_id))).scalar_one_or_none()

    def add(self, show: Show):
        self.db.add(show)
