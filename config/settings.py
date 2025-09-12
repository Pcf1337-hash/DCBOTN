from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class BotSettings(BaseSettings):
    """Bot configuration using Pydantic for validation and type safety."""
    
    # Discord Configuration
    discord_token: str = Field(..., env="DISCORD_BOT_TOKEN")
    command_prefix: str = Field(default="!", env="COMMAND_PREFIX")
    
    # Music Configuration
    max_queue_size: int = Field(default=50, env="MAX_QUEUE_SIZE")
    default_volume: float = Field(default=0.8, env="DEFAULT_VOLUME", ge=0.0, le=1.0)
    max_song_duration: int = Field(default=3600, env="MAX_SONG_DURATION")  # 1 hour
    download_timeout: int = Field(default=300, env="DOWNLOAD_TIMEOUT")  # 5 minutes
    
    # File System
    downloads_dir: str = Field(default="downloads", env="DOWNLOADS_DIR")
    intros_dir: str = Field(default="intros", env="INTROS_DIR")
    logs_dir: str = Field(default="logs", env="LOGS_DIR")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_max_bytes: int = Field(default=20*1024*1024, env="LOG_MAX_BYTES")  # 20MB
    log_backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")
    
    # Performance
    max_concurrent_downloads: int = Field(default=3, env="MAX_CONCURRENT_DOWNLOADS")
    cleanup_interval: int = Field(default=3600, env="CLEANUP_INTERVAL")  # 1 hour
    
    # UI Configuration
    progress_bar_length: int = Field(default=20, env="PROGRESS_BAR_LENGTH")
    progress_bar_filled: str = Field(default="▰", env="PROGRESS_BAR_FILLED")
    progress_bar_empty: str = Field(default="▱", env="PROGRESS_BAR_EMPTY")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        for directory in [self.downloads_dir, self.intros_dir, self.logs_dir]:
            os.makedirs(directory, exist_ok=True)

# Global settings instance
settings = BotSettings()