from typing import List
from utils.music_helpers import Song

class QueueManager:
    def __init__(self, max_size: int):
        self.queue: List[Song] = []
        self.max_size = max_size

    def add_song(self, song: Song) -> bool:
        if len(self.queue) < self.max_size:
            self.queue.append(song)
            return True
        return False

    def get_next_song(self) -> Song:
        return self.queue.pop(0) if self.queue else None

    def clear(self):
        self.queue.clear()

    def is_empty(self) -> bool:
        return len(self.queue) == 0

    def get_upcoming_songs(self, count: int) -> List[Song]:
        return self.queue[:count]

    def shuffle(self):
        import random
        random.shuffle(self.queue)

