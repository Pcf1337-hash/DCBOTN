from typing import List, Optional, Dict, Any
import random
import asyncio
from datetime import datetime, timedelta
from utils.music_helpers import Song
from utils.exceptions import QueueFullError
from utils.logger import get_logger
from utils.cache import cache_manager
from config.settings import settings

logger = get_logger('queue_manager')

class QueueManager:
    """Enhanced queue manager with persistence, history, and advanced features."""
    
    def __init__(self, max_size: int = None):
        self.queue: List[Song] = []
        self.max_size = max_size or settings.max_queue_size
        self.history: List[Song] = []
        self.max_history = 100
        self.shuffle_mode = False
        self.original_queue: List[Song] = []  # For unshuffle
        self._queue_lock = asyncio.Lock()
        
    async def add_song(self, song: Song, position: Optional[int] = None) -> bool:
        """Add song to queue at specified position or end."""
        async with self._queue_lock:
            if len(self.queue) >= self.max_size:
                raise QueueFullError(f"Queue is full (max {self.max_size} songs)")
            
            if position is not None and 0 <= position <= len(self.queue):
                self.queue.insert(position, song)
                logger.info("Song added to queue", title=song.title[:50], position=position)
            else:
                self.queue.append(song)
                logger.info("Song added to queue", title=song.title[:50], position=len(self.queue))
            
            await self._save_queue_state()
            return True
    
    async def add_songs(self, songs: List[Song]) -> int:
        """Add multiple songs to queue, returns number of songs added."""
        added = 0
        async with self._queue_lock:
            for song in songs:
                if len(self.queue) >= self.max_size:
                    break
                self.queue.append(song)
                added += 1
            
            if added > 0:
                logger.info("Multiple songs added to queue", count=added)
                await self._save_queue_state()
        
        return added

    async def get_next_song(self) -> Optional[Song]:
        """Get next song and move current to history."""
        async with self._queue_lock:
            if not self.queue:
                return None
            
            song = self.queue.pop(0)
            await self._add_to_history(song)
            await self._save_queue_state()
            
            logger.debug("Next song retrieved", title=song.title[:50])
            return song
    
    async def remove_song(self, index: int) -> Optional[Song]:
        """Remove song at specific index."""
        async with self._queue_lock:
            if 0 <= index < len(self.queue):
                song = self.queue.pop(index)
                logger.info("Song removed from queue", title=song.title[:50], index=index)
                await self._save_queue_state()
                return song
            return None
    
    async def move_song(self, from_index: int, to_index: int) -> bool:
        """Move song from one position to another."""
        async with self._queue_lock:
            if (0 <= from_index < len(self.queue) and 
                0 <= to_index < len(self.queue)):
                song = self.queue.pop(from_index)
                self.queue.insert(to_index, song)
                logger.info(
                    "Song moved in queue",
                    title=song.title[:50],
                    from_index=from_index,
                    to_index=to_index
                )
                await self._save_queue_state()
                return True
            return False

    async def clear(self):
        """Clear the queue and cleanup files."""
        async with self._queue_lock:
            for song in self.queue:
                song.cleanup()
            self.queue.clear()
            self.original_queue.clear()
            self.shuffle_mode = False
            
            logger.info("Queue cleared")
            await self._save_queue_state()

    def is_empty(self) -> bool:
        return len(self.queue) == 0
    
    def size(self) -> int:
        return len(self.queue)

    def get_upcoming_songs(self, count: int) -> List[Song]:
        """Get upcoming songs with limit."""
        return self.queue[:count]
    
    async def shuffle(self):
        """Shuffle the queue with ability to unshuffle."""
        async with self._queue_lock:
            if len(self.queue) <= 1:
                return
            
            if not self.shuffle_mode:
                # Save original order before shuffling
                self.original_queue = self.queue.copy()
                self.shuffle_mode = True
            
            random.shuffle(self.queue)
            logger.info("Queue shuffled", size=len(self.queue))
            await self._save_queue_state()
    
    async def unshuffle(self):
        """Restore original queue order."""
        async with self._queue_lock:
            if self.shuffle_mode and self.original_queue:
                # Restore songs that are still in queue
                current_urls = {song.url for song in self.queue}
                restored_queue = [
                    song for song in self.original_queue 
                    if song.url in current_urls
                ]
                
                self.queue = restored_queue
                self.shuffle_mode = False
                self.original_queue.clear()
                
                logger.info("Queue unshuffled", size=len(self.queue))
                await self._save_queue_state()
    
    def get_queue_info(self) -> Dict[str, Any]:
        """Get comprehensive queue information."""
        total_duration = sum(song.duration for song in self.queue)
        avg_duration = total_duration / len(self.queue) if self.queue else 0
        
        # Calculate estimated time until each song
        estimated_times = []
        cumulative_time = 0
        for song in self.queue:
            estimated_times.append(cumulative_time)
            cumulative_time += song.duration
        
        return {
            'size': len(self.queue),
            'max_size': self.max_size,
            'total_duration': total_duration,
            'total_duration_formatted': self._format_duration(total_duration),
            'average_duration': avg_duration,
            'is_full': len(self.queue) >= self.max_size,
            'is_shuffled': self.shuffle_mode,
            'estimated_times': estimated_times,
            'unique_requesters': len(set(song.requester.id for song in self.queue))
        }
    
    def get_history(self, count: int = 10) -> List[Song]:
        """Get recently played songs."""
        return self.history[-count:]
    
    def get_user_songs(self, user_id: int) -> List[Song]:
        """Get all songs in queue requested by specific user."""
        return [song for song in self.queue if song.requester.id == user_id]
    
    async def remove_user_songs(self, user_id: int) -> int:
        """Remove all songs from specific user."""
        async with self._queue_lock:
            original_size = len(self.queue)
            self.queue = [song for song in self.queue if song.requester.id != user_id]
            removed_count = original_size - len(self.queue)
            
            if removed_count > 0:
                logger.info("User songs removed", user_id=user_id, count=removed_count)
                await self._save_queue_state()
            
            return removed_count
    
    async def _add_to_history(self, song: Song):
        """Add song to history and maintain max size."""
        self.history.append(song)
        if len(self.history) > self.max_history:
            # Cleanup old song file
            old_song = self.history.pop(0)
            # Don't cleanup immediately, might be in use
            asyncio.create_task(self._delayed_cleanup(old_song))
    
    async def _delayed_cleanup(self, song: Song, delay: int = 300):
        """Cleanup song file after delay."""
        await asyncio.sleep(delay)  # Wait 5 minutes
        song.cleanup()
    
    async def _save_queue_state(self):
        """Save queue state to cache for persistence."""
        try:
            queue_data = {
                'songs': [song.to_dict() for song in self.queue],
                'shuffle_mode': self.shuffle_mode,
                'timestamp': datetime.now().isoformat()
            }
            await cache_manager.set('queue_state', queue_data, ttl=3600)
        except Exception as e:
            logger.error("Failed to save queue state", error=str(e))
    
    async def load_queue_state(self, bot):
        """Load queue state from cache."""
        try:
            queue_data = await cache_manager.get('queue_state')
            if not queue_data:
                return
            
            # Check if state is not too old (1 hour)
            saved_time = datetime.fromisoformat(queue_data['timestamp'])
            if datetime.now() - saved_time > timedelta(hours=1):
                logger.info("Queue state too old, skipping restore")
                return
            
            # Restore songs (need to recreate Song objects with current bot users)
            restored_songs = []
            for song_dict in queue_data['songs']:
                try:
                    # Try to get user from bot
                    user = bot.get_user(song_dict['requester_id'])
                    if user:
                        song_dict['requester'] = user
                        # Remove file_path as files might not exist
                        song_dict.pop('file_path', None)
                        restored_songs.append(Song(**song_dict))
                except Exception as e:
                    logger.warning("Failed to restore song", error=str(e))
                    continue
            
            async with self._queue_lock:
                self.queue = restored_songs
                self.shuffle_mode = queue_data.get('shuffle_mode', False)
            
            logger.info("Queue state restored", count=len(restored_songs))
            
        except Exception as e:
            logger.error("Failed to load queue state", error=str(e))
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to readable string."""
        if seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} Min"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    async def cleanup_all(self):
        """Cleanup all downloaded files."""
        async with self._queue_lock:
            for song in self.queue + self.history:
                song.cleanup()
            self.history.clear()
            logger.info("All queue files cleaned up")