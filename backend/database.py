"""
DataForge AI - Database layer (SQLAlchemy)
SQLite by default; DATABASE_URL can point to PostgreSQL for production
(e.g. Render + managed Postgres) without any code changes.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from backend import models  # noqa: F401  (ensure models are registered)
    Base.metadata.create_all(bind=engine)
