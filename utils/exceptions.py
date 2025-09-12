"""Custom exceptions for the music bot."""

class MusicBotException(Exception):
    """Base exception for music bot errors."""
    pass

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