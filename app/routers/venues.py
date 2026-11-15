
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.entities import Venue, User
from app.schemas.venue import (
    VenueCreate,
    VenueUpdate,
    VenueResponse
)
from app.security.dependencies import require_admin


router = APIRouter(
    prefix="/api/venues",
    tags=["Venue Management"]
)


# 1. View all venues
@router.get("/", response_model=list[VenueResponse])
def get_all_venues(db: Session = Depends(get_db)):
    venues = db.query(Venue).order_by(Venue.id.desc()).all()
    return venues


# 2. View one venue
@router.get("/{venue_id}", response_model=VenueResponse)
def get_venue(venue_id: int, db: Session = Depends(get_db)):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()

    if not venue:
        raise HTTPException(
            status_code=404,
            detail="Venue not found"
        )

    return venue


# 3. Create a venue (Admin only)
@router.post("/", response_model=VenueResponse, status_code=201)
def create_venue(
    data: VenueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    new_venue = Venue(
        name=data.name,
        location=data.location,
        capacity=data.capacity,
        description=data.description,
        image=data.image,
        hourly_hire_rate=data.hourly_hire_rate,
        open_for_private_hire=data.open_for_private_hire
    )

    db.add(new_venue)
    db.commit()
    db.refresh(new_venue)

    return new_venue


# 4. Update a venue (Admin only)
@router.put("/{venue_id}", response_model=VenueResponse)
def update_venue(
    venue_id: int,
    data: VenueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()

    if not venue:
        raise HTTPException(
            status_code=404,
            detail="Venue not found"
        )

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(venue, field, value)

    db.commit()
    db.refresh(venue)

    return venue
