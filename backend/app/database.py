from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


def _get_connect_args(url: str) -> dict:
    """Use SSL only for remote hosts (Supabase). Skip for localhost/dev."""
    is_local = any(h in url for h in ("localhost", "127.0.0.1", "sqlite"))
    return {} if is_local else {"sslmode": "require"}


engine = create_engine(
    settings.database_url_fixed,
    connect_args=_get_connect_args(settings.database_url_fixed),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
