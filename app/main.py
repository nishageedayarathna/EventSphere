
import asyncio
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import inspect
from fastapi.responses import FileResponse

from app.database.connection import (
    create_database,
    engine,
    SessionLocal
)

from app.agents.waitlist_agent import waitlist_agent

# API routers
from app.routers.auth import router as auth_router
from app.routers.access import router as access_router
from app.routers.venues import router as venues_router
from app.routers.events import router as events_router
from app.routers.bookings import router as bookings_router
from app.routers.checkin import router as checkin_router
from app.routers.cancellations import router as cancellations_router
from app.routers.venue_hire import router as venue_hire_router
from app.routers import waitlist
from app.routers.admin import router as admin_router
from app.routers.notifications import router as notifications_router


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
app.include_router(cancellations_router)
app.include_router(venue_hire_router)
app.include_router(waitlist.router)
app.include_router(checkin_router)
app.include_router(admin_router)
app.include_router(notifications_router)

# --------------------------------------------------
# WAITLIST BACKGROUND SCHEDULER
# --------------------------------------------------

async def waitlist_expiry_scheduler():
    """
    Automatically checks expired waitlist offers
    every 30 seconds.
    """

    while True:
        db = SessionLocal()

        try:
            result = waitlist_agent.expire_offers(db)

            if result.get("expired_count", 0) > 0:
                print("Waitlist expiry:", result)

        except Exception as error:
            db.rollback()
            print("Waitlist scheduler error:", error)

        finally:
            db.close()

        await asyncio.sleep(30)


waitlist_scheduler_task = None


# --------------------------------------------------
# DATABASE INITIALIZATION AND SCHEDULER START
# --------------------------------------------------

@app.on_event("startup")
async def startup():
    global waitlist_scheduler_task

    create_database()

    waitlist_scheduler_task = asyncio.create_task(
        waitlist_expiry_scheduler()
    )

    print("EventSphere database initialized.")
    print("Waitlist expiry scheduler started.")


# --------------------------------------------------
# STOP SCHEDULER WHEN SERVER SHUTS DOWN
# --------------------------------------------------

@app.on_event("shutdown")
async def shutdown():
    global waitlist_scheduler_task

    if waitlist_scheduler_task:
        waitlist_scheduler_task.cancel()

        try:
            await waitlist_scheduler_task
        except asyncio.CancelledError:
            pass

    print("Waitlist expiry scheduler stopped.")


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


@app.get("/dashboard")
def dashboard_page():
    return FileResponse(STATIC_DIR / "dashboard.html")