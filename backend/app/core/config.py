from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables (or a .env file)."""

    PROJECT_NAME: str = "DocuMind AI"
    API_PREFIX: str = "/api"

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/documind"

    # AI
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-opus-4-8"
    LLM_MAX_TOKENS: int = 8192

    # Storage
    UPLOAD_DIR: str = "./uploads"
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    MAX_UPLOAD_SIZE_MB: int = 20

    # RAG tuning
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 5

    # CORS (comma-separated origins)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
