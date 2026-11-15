from fastapi import APIRouter, Depends

from app.models.entities import User
from app.security.dependencies import (
    require_admin,
    require_staff,
    require_attendee
)


router = APIRouter(tags=["Role Access"])


# ADMIN ACCESS CHECK
@router.get("/api/admin/access-check")
def admin_access(
    current_user: User = Depends(require_admin)
):

    return {
        "message": "Admin access granted",
        "user": current_user.full_name,
        "role": current_user.role
    }


# STAFF ACCESS CHECK
@router.get("/api/staff/access-check")
def staff_access(
    current_user: User = Depends(require_staff)
):

    return {
        "message": "Staff access granted",
        "user": current_user.full_name,
        "role": current_user.role
    }


# ATTENDEE ACCESS CHECK
@router.get("/api/attendee/access-check")
def attendee_access(
    current_user: User = Depends(require_attendee)
):

    return {
        "message": "Attendee access granted",
        "user": current_user.full_name,
        "role": current_user.role
    }