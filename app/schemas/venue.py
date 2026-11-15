
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    location: str = Field(min_length=2, max_length=255)
    capacity: int = Field(gt=0)
    description: Optional[str] = None
    image: Optional[str] = None
    hourly_hire_rate: float = Field(ge=0)
    open_for_private_hire: bool = True


class VenueUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    location: Optional[str] = Field(default=None, min_length=2, max_length=255)
    capacity: Optional[int] = Field(default=None, gt=0)
    description: Optional[str] = None
    image: Optional[str] = None
    hourly_hire_rate: Optional[float] = Field(default=None, ge=0)
    open_for_private_hire: Optional[bool] = None


class VenueResponse(BaseModel):
    id: int
    name: str
    location: str
    capacity: int
    description: Optional[str]
    image: Optional[str]
    hourly_hire_rate: float
    open_for_private_hire: bool

    model_config = ConfigDict(from_attributes=True)
