
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# Project root directory
BASE_DIR = Path(__file__).resolve().parents[2]


# Database configuration
# Use PostgreSQL when DATABASE_URL is provided.
# Otherwise, use SQLite locally.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{BASE_DIR / 'eventsphere.db'}"


# Support Render PostgreSQL connection URLs with Psycopg 3
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )

elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )


# Configure database engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )


# Create database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# Base class for database models
Base = declarative_base()


# Database dependency for FastAPI routes
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# Create all database tables
def create_database():
    # Import models before creating tables
    from app.models import entities

    Base.metadata.create_all(bind=engine)
