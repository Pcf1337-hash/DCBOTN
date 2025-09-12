"""Enhanced custom exceptions for the music bot."""

class MusicBotException(Exception):
    """Base exception for music bot errors."""
    
    def __init__(self, message: str, error_code: str = None, **kwargs):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = kwargs

class AudioDownloadError(MusicBotException):
    """Raised when audio download fails."""
    pass

class PlaybackError(MusicBotException):
    """Raised when audio playback fails."""
    pass

class QueueFullError(MusicBotException):
    """Raised when trying to add to a full queue."""
    pass

class InvalidTimeFormatError(MusicBotException):
    """Raised when time format is invalid."""
    pass

class VoiceConnectionError(MusicBotException):
    """Raised when voice connection fails."""
    pass

class PermissionError(MusicBotException):
    """Raised when bot lacks required permissions."""
    pass

class RateLimitError(MusicBotException):
    """Raised when rate limits are exceeded."""
    pass

class ConfigurationError(MusicBotException):
    """Raised when configuration is invalid."""
    pass

class DatabaseError(MusicBotException):
    """Raised when database operations fail."""
    pass

class CacheError(MusicBotException):
    """Raised when cache operations fail."""
    pass

class ValidationError(MusicBotException):
    """Raised when input validation fails."""
    pass