from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List
import os
from pathlib import Path

class BotSettings(BaseSettings):
    """Enhanced bot configuration with validation and type safety."""
    
    # Discord Configuration
    discord_token: str = Field(..., env="DISCORD_BOT_TOKEN")
    command_prefix: str = Field(default="!", env="COMMAND_PREFIX")
    owner_ids: List[int] = Field(default_factory=list, env="OWNER_IDS")
    
    # Music Configuration
    max_queue_size: int = Field(default=100, env="MAX_QUEUE_SIZE", ge=1, le=500)
    default_volume: float = Field(default=0.8, env="DEFAULT_VOLUME", ge=0.0, le=1.0)
    max_song_duration: int = Field(default=7200, env="MAX_SONG_DURATION", ge=60)  # 2 hours
    download_timeout: int = Field(default=300, env="DOWNLOAD_TIMEOUT", ge=30)
    max_playlist_size: int = Field(default=50, env="MAX_PLAYLIST_SIZE", ge=1, le=200)
    
    # Performance & Limits
    max_concurrent_downloads: int = Field(default=3, env="MAX_CONCURRENT_DOWNLOADS", ge=1, le=10)
    cleanup_interval: int = Field(default=1800, env="CLEANUP_INTERVAL", ge=300)  # 30 minutes
    max_memory_usage_mb: int = Field(default=512, env="MAX_MEMORY_USAGE_MB", ge=128)
    
    # File System
    downloads_dir: Path = Field(default=Path("downloads"), env="DOWNLOADS_DIR")
    intros_dir: Path = Field(default=Path("intros"), env="INTROS_DIR")
    logs_dir: Path = Field(default=Path("logs"), env="LOGS_DIR")
    cache_dir: Path = Field(default=Path("cache"), env="CACHE_DIR")
    
    # Database (Optional)
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_max_bytes: int = Field(default=50*1024*1024, env="LOG_MAX_BYTES")  # 50MB
    log_backup_count: int = Field(default=10, env="LOG_BACKUP_COUNT")
    enable_json_logging: bool = Field(default=False, env="ENABLE_JSON_LOGGING")
    
    # Monitoring
    enable_metrics: bool = Field(default=False, env="ENABLE_METRICS")
    metrics_port: int = Field(default=8000, env="METRICS_PORT", ge=1024, le=65535)
    
    # UI Configuration
    progress_bar_length: int = Field(default=25, env="PROGRESS_BAR_LENGTH", ge=10, le=50)
    progress_bar_filled: str = Field(default="█", env="PROGRESS_BAR_FILLED")
    progress_bar_empty: str = Field(default="░", env="PROGRESS_BAR_EMPTY")
    embed_color: int = Field(default=0x00ff00, env="EMBED_COLOR")
    
    # Feature Flags
    enable_slash_commands: bool = Field(default=True, env="ENABLE_SLASH_COMMANDS")
    enable_auto_disconnect: bool = Field(default=True, env="ENABLE_AUTO_DISCONNECT")
    auto_disconnect_timeout: int = Field(default=300, env="AUTO_DISCONNECT_TIMEOUT", ge=60)
    enable_user_playlists: bool = Field(default=False, env="ENABLE_USER_PLAYLISTS")
    enable_web_interface: bool = Field(default=True, env="ENABLE_WEB_INTERFACE")
    web_port: int = Field(default=3000, env="WEB_PORT", ge=1024, le=65535)
    
    @validator('owner_ids', pre=True)
    def parse_owner_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip().isdigit()]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        for directory in [self.downloads_dir, self.intros_dir, self.logs_dir, self.cache_dir]:
            directory.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = BotSettings()