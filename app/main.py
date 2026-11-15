
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import inspect

from app.database.connection import create_database, engine

from app.routers.auth import router as auth_router
from app.routers.access import router as access_router
from app.routers.venues import router as venues_router
from app.routers.events import router as events_router
from app.routers.bookings import router as bookings_router
from app.routers.checkin import router as checkin_router

# --------------------------------------------------
# PROJECT DIRECTORIES
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="EventSphere",
    description="University Event and Venue Booking Platform",
    version="1.0.0"
)


# --------------------------------------------------
# SESSION MIDDLEWARE
# --------------------------------------------------

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get(
        "SESSION_SECRET",
        "local-development-secret-change-before-deployment"
    ),
    same_site="lax",
    https_only=os.environ.get("ENVIRONMENT") == "production"
)


# --------------------------------------------------
# STATIC FILES
# --------------------------------------------------

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)


# --------------------------------------------------
# REGISTER API ROUTERS
# --------------------------------------------------

app.include_router(auth_router)
app.include_router(access_router)
app.include_router(venues_router)
app.include_router(events_router)
app.include_router(bookings_router)
app.include_router(checkin_router)


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

@app.on_event("startup")
def startup():
    create_database()


# --------------------------------------------------
# FRONTEND PAGES
# --------------------------------------------------

@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/register", include_in_schema=False)
def register_page():
    return FileResponse(STATIC_DIR / "register.html")


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/api/health")
def health_check():
    return {
        "application": "EventSphere",
        "status": "running",
        "message": "EventSphere backend is working"
    }


# --------------------------------------------------
# DATABASE STATUS
# --------------------------------------------------

@app.get("/api/database")
def database_status():

    inspector = inspect(engine)

    return {
        "database": "SQLite",
        "status": "connected",
        "tables": inspector.get_table_names()
    }
