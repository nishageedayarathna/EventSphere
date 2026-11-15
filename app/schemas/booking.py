
from pydantic import BaseModel, Field, ConfigDict


class BookingCreate(BaseModel):
    event_id: int = Field(gt=0)
    ticket_category_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=6)


class BookingResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    ticket_category_id: int
    quantity: int
    total_amount: float
    status: str

    model_config = ConfigDict(from_attributes=True)
