from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Flask → FastAPI: no SECRET_KEY needed for sessions, only JWT
    SECRET_KEY: str = "dev-secret-key"
    JWT_SECRET_KEY: str = "dev-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database — Supabase PostgreSQL
    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/medassist"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_PRIMARY: str = "gpt-4o"
    OPENAI_MODEL_FAST: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"

    # App
    APP_ENV: str = "development"
    DEBUG: bool = True

    @property
    def database_url_fixed(self) -> str:
        """Supabase returns postgres:// — SQLAlchemy needs postgresql://"""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    model_config = {"env_file": ".env", "case_sensitive": True}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
