from pydantic import BaseModel, ConfigDict
from typing import List
from uuid import UUID

class ShowCreate(BaseModel):
    name: str
    seats: List[str]
    price_paise: int

class ShowResponse(BaseModel):
    id: UUID
    name: str
    price_paise: int
    total_seats: int
    model_config = ConfigDict(from_attributes=True)

class ReserveRequest(BaseModel):
    seats: List[str]

class ReserveResponse(BaseModel):
    reservation_id: UUID
    show_id: UUID
    user_id: str
    seats: List[str]
    amount_paise: int
    status: str
