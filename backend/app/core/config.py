from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Known-insecure fallback so `git clone && uvicorn` works out of the box.
# main.py refuses to start in production if this value is still in use.
DEV_SECRET_KEY = "dev-secret-key-change-in-production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables (or a .env file)."""

    PROJECT_NAME: str = "DocuMind AI"
    API_PREFIX: str = "/api"

    # "development" or "production". Production enforces a real SECRET_KEY.
    ENVIRONMENT: str = "development"

    # Security
    SECRET_KEY: str = DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    # Short-lived access tokens; sessions stay alive via rotating refresh tokens.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate limiting (disabled in the test suite)
    RATE_LIMIT_ENABLED: bool = True

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/documind"

    # AI provider: "demo" (no API, canned responses), "groq" (free tier), or "anthropic".
    # Demo is the default so the project runs with zero API keys and zero cost.
    LLM_PROVIDER: str = "demo"
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-opus-4-8"
    LLM_MAX_TOKENS: int = 8192
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

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

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
