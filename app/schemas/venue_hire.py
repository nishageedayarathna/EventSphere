
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator


class VenueHireCreate(BaseModel):
    venue_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime
    purpose: str = Field(min_length=5, max_length=500)
    guest_count: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class VenueHireDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    admin_note: str = Field(default="", max_length=500)


class VenueHireResponse(BaseModel):
    id: int
    user_id: int
    venue_id: int
    start_time: datetime
    end_time: datetime
    purpose: str
    guest_count: int
    quoted_price: float
    status: str

    model_config = ConfigDict(from_attributes=True)
