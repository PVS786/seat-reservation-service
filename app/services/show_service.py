from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models import Show, Seat
from app.schemas import ShowCreate
from app.repositories.show_repository import ShowRepository
from app.repositories.seat_repository import SeatRepository

class ShowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.show_repo = ShowRepository(db)
        self.seat_repo = SeatRepository(db)

    async def create_show(self, show_in: ShowCreate) -> Show:
        if not show_in.seats:
            raise HTTPException(status_code=400, detail="Must provide at least one seat")
            
        if len(show_in.seats) != len(set(show_in.seats)):
            raise HTTPException(status_code=400, detail="Duplicate seats in request")

        new_show = Show(
            name=show_in.name,
            price_paise=show_in.price_paise,
            total_seats=len(show_in.seats)
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
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to create show")

        return new_show
