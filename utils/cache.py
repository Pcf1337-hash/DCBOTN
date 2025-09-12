"""Enhanced caching system for the music bot."""

import asyncio
import json
import time
from typing import Any, Optional, Dict, List
from pathlib import Path
from config.settings import settings
from utils.logger import get_logger

logger = get_logger('cache')

class CacheManager:
    """Enhanced cache manager with TTL and persistence."""
    
    def __init__(self):
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_file = settings.cache_dir / "bot_cache.json"
        self.default_ttl = 3600  # 1 hour
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Filter out expired entries
                    current_time = time.time()
                    self.memory_cache = {
                        k: v for k, v in data.items()
                        if v.get('expires_at', 0) > current_time
                    }
                logger.info("Cache loaded", entries=len(self.memory_cache))
        except Exception as e:
            logger.error("Failed to load cache", error=str(e))
            self.memory_cache = {}
    
    async def save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory_cache, f, indent=2)
            logger.debug("Cache saved to disk")
        except Exception as e:
            logger.error("Failed to save cache", error=str(e))
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if entry['expires_at'] > time.time():
                logger.debug("Cache hit", key=key)
                return entry['value']
            else:
                # Remove expired entry
                del self.memory_cache[key]
                logger.debug("Cache expired", key=key)
        
        logger.debug("Cache miss", key=key)
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        ttl = ttl or self.default_ttl
        expires_at = time.time() + ttl
        
        self.memory_cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': time.time()
        }
        
        logger.debug("Cache set", key=key, ttl=ttl)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self.memory_cache:
            del self.memory_cache[key]
            logger.debug("Cache deleted", key=key)
            return True
        return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        self.memory_cache.clear()
        logger.info("Cache cleared")
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries and return count."""
        current_time = time.time()
        expired_keys = [
            k for k, v in self.memory_cache.items()
            if v['expires_at'] <= current_time
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        if expired_keys:
            logger.info("Expired cache entries removed", count=len(expired_keys))
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        total_entries = len(self.memory_cache)
        expired_entries = sum(
            1 for v in self.memory_cache.values()
            if v['expires_at'] <= current_time
        )
        
        return {
            'total_entries': total_entries,
            'active_entries': total_entries - expired_entries,
            'expired_entries': expired_entries,
            'cache_file_exists': self.cache_file.exists()
        }

# Global cache instance
cache_manager = CacheManager()