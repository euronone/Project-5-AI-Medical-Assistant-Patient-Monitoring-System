import os
from dotenv import load_dotenv

load_dotenv()


def _build_db_uri() -> str:
    """
    Build the SQLAlchemy database URI.
    Supabase provides a connection string starting with 'postgres://'
    but SQLAlchemy requires 'postgresql://'. This function normalises it.
    """
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://user:pass@localhost:5432/medassist",
    )
    # Supabase sometimes returns 'postgres://' — SQLAlchemy needs 'postgresql://'
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret")
    SQLALCHEMY_DATABASE_URI = _build_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Supabase requires SSL — these engine options enforce it
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "sslmode": "require",
        },
        "pool_pre_ping": True,       # Detect dropped connections
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 300,         # Recycle connections every 5 minutes
    }

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
    )
    JWT_ACCESS_TOKEN_EXPIRES = 900       # 15 minutes
    JWT_REFRESH_TOKEN_EXPIRES = 604800   # 7 days


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # No SSL needed for in-memory SQLite
    SQLALCHEMY_ENGINE_OPTIONS = {}


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
