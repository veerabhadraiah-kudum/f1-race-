import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    env: str = os.getenv("ENV", "development")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    openf1_base_url: str = os.getenv("OPENF1_BASE_URL", "https://api.openf1.org/v1")
    jolpica_base_url: str = os.getenv("JOLPICA_BASE_URL", "https://api.jolpi.ca/ergast/f1")
    fastf1_cache_dir: str = os.getenv("FASTF1_CACHE_DIR", "./data/cache")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    mock_mode: bool = os.getenv("MOCK_MODE", "false").lower() == "true"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
# Ensure cache dir exists
Path(settings.fastf1_cache_dir).mkdir(parents=True, exist_ok=True)
