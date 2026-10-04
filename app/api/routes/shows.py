from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import ShowCreate, ShowResponse, ShowDetailResponse
from app.auth import require_admin
from app.services.show_service import ShowService

router = APIRouter(prefix="/shows", tags=["shows"])

def get_show_service(db: AsyncSession = Depends(get_db)) -> ShowService:
    return ShowService(db)

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ShowResponse)
async def create_show(
    show_in: ShowCreate, 
    admin_id: str = Depends(require_admin),
    service: ShowService = Depends(get_show_service)
):
    return await service.create_show(show_in)

@router.get("/{show_id}", status_code=status.HTTP_200_OK, response_model=ShowDetailResponse)
async def get_show(show_id: str, service: ShowService = Depends(get_show_service)):
    return await service.get_show_detail(show_id)
