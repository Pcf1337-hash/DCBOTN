import logging
import structlog
from logging.handlers import RotatingFileHandler
from config.settings import settings
import sys
from pathlib import Path
from typing import Any, Dict

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.enable_json_logging else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Suppress noisy loggers
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.client').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('yt_dlp').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.WARNING)

class ColoredFormatter(logging.Formatter):
    """Enhanced colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{self.BOLD}{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

class StructuredFormatter(logging.Formatter):
    """Enhanced structured formatter for file output."""
    
    def format(self, record):
        # Add extra context if available
        extra_info = []
        for attr in ['user_id', 'guild_id', 'command', 'duration', 'memory_usage']:
            if hasattr(record, attr):
                extra_info.append(f"{attr}={getattr(record, attr)}")
        
        extra_str = f" [{', '.join(extra_info)}]" if extra_info else ""
        return f"{self.formatTime(record)} - {record.name} - {record.levelname} - {record.getMessage()}{extra_str}"

def setup_logger(name='bot', log_file=None, level=None):
    """Enhanced logger setup with better configuration."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.log_level.upper()))
        logger.propagate = False
        
        # File handler with rotation
        if log_file is None:
            log_file = settings.logs_dir / f"{name}.log"
        
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=settings.log_max_bytes, 
            backupCount=settings.log_backup_count, 
            encoding='utf-8'
        )
        
        if settings.enable_json_logging:
            file_handler.setFormatter(logging.Formatter('%(message)s'))
        else:
            file_handler.setFormatter(StructuredFormatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        if sys.stdout.isatty() and not settings.enable_json_logging:
            console_handler.setFormatter(ColoredFormatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            ))
        else:
            console_handler.setFormatter(StructuredFormatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)

class LoggerMixin:
    """Enhanced mixin with structured logging capabilities."""
    
    @property
    def logger(self) -> structlog.BoundLogger:
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__.lower())
        return self._logger
    
    def log_command(self, ctx, command_name: str, **kwargs):
        """Log command execution with enhanced context."""
        self.logger.info(
            "Command executed",
            command=command_name,
            user_id=ctx.author.id,
            guild_id=ctx.guild.id if ctx.guild else None,
            channel_id=ctx.channel.id,
            **kwargs
        )
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics."""
        self.logger.info(
            "Performance metric",
            operation=operation,
            duration=duration,
            **kwargs
        )