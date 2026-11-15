
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TicketCategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    price: float = Field(ge=0)
    quantity: int = Field(gt=0)


class TicketCategoryResponse(BaseModel):
    id: int
    event_id: int
    name: str
    price: float
    quantity: int
    sold_quantity: int

    model_config = ConfigDict(from_attributes=True)


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    category: str = Field(min_length=2, max_length=100)
    venue_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime
    description: str = ""
    status: Literal["draft", "published"] = "draft"

    ticket_categories: list[TicketCategoryCreate] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_event(self):
        if self.end_time <= self.start_time:
            raise ValueError(
                "End time must be after start time"
            )

        total_tickets = sum(
            ticket.quantity
            for ticket in self.ticket_categories
        )

        if total_tickets <= 0:
            raise ValueError(
                "At least one ticket category is required"
            )

        return self


class EventUpdate(BaseModel):
    title: Optional[str] = Field(
        default=None, min_length=3, max_length=180
    )
    category: Optional[str] = Field(
        default=None, min_length=2, max_length=100
    )
    venue_id: Optional[int] = Field(default=None, gt=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None


class EventResponse(BaseModel):
    id: int
    title: str
    category: str
    venue_id: int
    start_time: datetime
    end_time: datetime
    description: str
    status: str
    created_by: int

    model_config = ConfigDict(from_attributes=True)
