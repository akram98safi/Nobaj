"""Application settings and environment configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app.core.constants import UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR, BASE_DIR, DATA_DIR


class Settings(BaseSettings):
    """Nobaj configuration parameters."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General
    APP_NAME: str = "Nobaj"
    APP_DESCRIPTION: str = "Modern High-Performance Online Media Suite"
    PUBLIC_BASE_URL: str = "https://nobaj.com"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    ADMIN_TOKEN: str = ""  # Required to access /admin and /api/stats/admin
    GOOGLE_ADSENSE_CLIENT: str = ""
    GOOGLE_ADSENSE_SLOT_TOP: str = ""
    GOOGLE_ADSENSE_SLOT_BOTTOM: str = ""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Storage paths
    UPLOAD_PATH: Path = UPLOAD_DIR
    OUTPUT_PATH: Path = OUTPUT_DIR
    TEMP_PATH: Path = TEMP_DIR
    ANALYTICS_DB_PATH: Path = DATA_DIR / "analytics" / "analytics.sqlite3"

    # Upload & Processing Limits
    MAX_UPLOAD_SIZE_MB: int = 500  # 500 Megabytes
    MAX_DURATION_SECONDS: int = 1800  # 30 Minutes
    
    # Concurrency & Queueing
    MAX_CONCURRENT_JOBS: int = 2  # Max simultaneous FFmpeg processes (tune for CPU/RAM)
    MAX_QUEUE_SIZE: int = 50      # Maximum queued jobs waiting
    
    # Auto-cleanup Settings
    FILE_TTL_MINUTES: int = 30     # Files older than 30 mins are purged
    CLEANUP_INTERVAL_MINUTES: int = 5 # Check every 5 minutes

    # Hardware Acceleration
    ENABLE_GPU: bool = True       # Detect and leverage NVENC/QSV/VAAPI if available

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def ensure_directories(self) -> None:
        """Ensure all runtime directories exist."""
        self.UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
        self.TEMP_PATH.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
