import logging
from logging.handlers import RotatingFileHandler
from config.settings import settings
import sys
from pathlib import Path

# Suppress noisy loggers
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('yt_dlp').setLevel(logging.WARNING)

class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

class StructuredFormatter(logging.Formatter):
    """Structured formatter for file output."""
    
    def format(self, record):
        # Add extra context if available
        extra_info = ""
        if hasattr(record, 'user_id'):
            extra_info += f" [User: {record.user_id}]"
        if hasattr(record, 'guild_id'):
            extra_info += f" [Guild: {record.guild_id}]"
        if hasattr(record, 'command'):
            extra_info += f" [Command: {record.command}]"
            
        return f"{self.formatTime(record)} - {record.name} - {record.levelname} - {record.getMessage()}{extra_info}"

def setup_logger(name='bot', log_file=None, level=None):
    """Setup logger with both file and console handlers."""
    logger = logging.getLogger(name)
    
    # Only setup if logger doesn't have handlers
    if not logger.handlers:
        logger.setLevel(level or settings.log_level)
        logger.propagate = False
        
        # File handler
        if log_file is None:
            log_file = Path(settings.logs_dir) / f"{name}.log"
        
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=settings.log_max_bytes, 
            backupCount=settings.log_backup_count, 
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # Console handler
        stream_handler = logging.StreamHandler()
        if sys.stdout.isatty():  # Only use colors in terminal
            stream_handler.setFormatter(ColoredFormatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            ))
        else:
            stream_handler.setFormatter(StructuredFormatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        
        logger.propagate = False
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with consistent configuration."""
    return setup_logger(name)

class LoggerMixin:
    """Mixin to add logging capabilities to classes."""
    
    @property
    def logger(self) -> logging.Logger:
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__.lower())
        return self._logger
    
    def log_command(self, ctx, command_name: str, **kwargs):
        """Log command execution with context."""
        extra = {
            'user_id': ctx.author.id,
            'guild_id': ctx.guild.id if ctx.guild else None,
            'command': command_name
        }
        self.logger.info(f"Command executed: {command_name}", extra=extra)

