from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.entities import User
from app.schemas.auth import RegisterRequest, LoginRequest
from app.services.auth_service import (
    hash_password,
    verify_password
)
from app.security.csrf import (
    create_csrf_token,
    verify_csrf_token
)
from app.security.dependencies import get_current_user


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


# GET CSRF TOKEN
@router.get("/csrf")
def get_csrf(request: Request):

    return {
        "csrf_token": create_csrf_token(request)
    }


# REGISTER ATTENDEE
@router.post(
    "/register",
    status_code=201,
    dependencies=[Depends(verify_csrf_token)]
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        User.email == data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email address is already registered"
        )

    new_user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role="attendee"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Registration successful",
        "user": {
            "id": new_user.id,
            "full_name": new_user.full_name,
            "email": new_user.email,
            "role": new_user.role
        }
    }


# LOGIN
@router.post(
    "/login",
    dependencies=[Depends(verify_csrf_token)]
)
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.email == data.email
    ).first()

    if not user or not verify_password(
        data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account is inactive"
        )

    # Clear the previous session to prevent session fixation
    request.session.clear()

    request.session["user_id"] = user.id

    # Create a new CSRF token for the authenticated session
    csrf_token = create_csrf_token(request)

    return {
        "message": "Login successful",
        "csrf_token": csrf_token,
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role
        }
    }


# CURRENT USER
@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user)
):

    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role
    }


# LOGOUT
@router.post(
    "/logout",
    dependencies=[Depends(verify_csrf_token)]
)
def logout(request: Request):

    request.session.clear()

    return {
        "message": "Logged out successfully"
    }