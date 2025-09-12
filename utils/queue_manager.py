from typing import List
import random
from utils.music_helpers import Song
from utils.exceptions import QueueFullError
from utils.logger import get_logger

logger = get_logger('queue_manager')

class QueueManager:
    """Enhanced queue manager with better functionality."""
    
    def __init__(self, max_size: int):
        self.queue: List[Song] = []
        self.max_size = max_size
        self.history: List[Song] = []
        self.max_history = 50

    def add_song(self, song: Song, position: int = None) -> bool:
        """Add song to queue at specified position or end."""
        if len(self.queue) < self.max_size:
            if position is not None and 0 <= position <= len(self.queue):
                self.queue.insert(position, song)
            else:
                self.queue.append(song)
            logger.debug(f"Added song to queue: {song.title}")
            return True
        raise QueueFullError(f"Queue is full (max {self.max_size} songs)")
    
    def add_songs(self, songs: List[Song]) -> int:
        """Add multiple songs to queue, returns number of songs added."""
        added = 0
        for song in songs:
            try:
                if self.add_song(song):
                    added += 1
            except QueueFullError:
                break
        return added

    def get_next_song(self) -> Song | None:
        """Get next song and move current to history."""
        if self.queue:
            song = self.queue.pop(0)
            self._add_to_history(song)
            return song
        return None
    
    def remove_song(self, index: int) -> Song | None:
        """Remove song at specific index."""
        if 0 <= index < len(self.queue):
            song = self.queue.pop(index)
            logger.debug(f"Removed song from queue: {song.title}")
            return song
        return None
    
    def move_song(self, from_index: int, to_index: int) -> bool:
        """Move song from one position to another."""
        if (0 <= from_index < len(self.queue) and 
            0 <= to_index < len(self.queue)):
            song = self.queue.pop(from_index)
            self.queue.insert(to_index, song)
            logger.debug(f"Moved song from {from_index} to {to_index}: {song.title}")
            return True
        return False

    def clear(self):
        """Clear the queue and cleanup files."""
        for song in self.queue:
            song.cleanup()
        self.queue.clear()
        logger.debug("Queue cleared")

    def is_empty(self) -> bool:
        return len(self.queue) == 0
    
    def size(self) -> int:
        return len(self.queue)

    def get_upcoming_songs(self, count: int) -> List[Song]:
        return self.queue[:count]
    
    def get_queue_info(self) -> dict:
        """Get detailed queue information."""
        total_duration = sum(song.duration for song in self.queue)
        return {
            'size': len(self.queue),
            'max_size': self.max_size,
            'total_duration': total_duration,
            'is_full': len(self.queue) >= self.max_size
        }

    def shuffle(self):
        """Shuffle the queue."""
        if len(self.queue) > 1:
            random.shuffle(self.queue)
            logger.debug("Queue shuffled")
    
    def get_history(self, count: int = 10) -> List[Song]:
        """Get recently played songs."""
        return self.history[-count:]
    
    def _add_to_history(self, song: Song):
        """Add song to history and maintain max size."""
        self.history.append(song)
        if len(self.history) > self.max_history:
            # Cleanup old song file
            old_song = self.history.pop(0)
            old_song.cleanup()
    
    def cleanup_all(self):
        """Cleanup all downloaded files."""
        for song in self.queue + self.history:
            song.cleanup()
        import random
        self.history.clear()
        logger.debug("All queue files cleaned up")

