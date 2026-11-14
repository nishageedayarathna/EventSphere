from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import inspect

from app.database.connection import create_database, engine
from app.routers.auth import router as auth_router


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="EventSphere",
    description="University Event and Venue Booking Platform",
    version="1.0.0"
)

# Signed session cookies
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get(
        "SESSION_SECRET",
        "local-development-secret-change-before-deployment"
    ),
    same_site="lax",
    https_only=os.environ.get("ENVIRONMENT") == "production"
)

# Static files
app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)

# Authentication routes
app.include_router(auth_router)


@app.on_event("startup")
def startup():
    create_database()


@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/register", include_in_schema=False)
def register_page():
    return FileResponse(STATIC_DIR / "register.html")


@app.get("/api/health")
def health_check():
    return {
        "application": "EventSphere",
        "status": "running",
        "message": "EventSphere backend is working"
    }


@app.get("/api/database")
def database_status():
    inspector = inspect(engine)

    return {
        "database": "SQLite",
        "status": "connected",
        "tables": inspector.get_table_names()
    }