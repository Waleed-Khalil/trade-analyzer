"""
Simple file-based cache with TTL
"""

import os
import json
import time
from typing import Any, Optional
from pathlib import Path


class SimpleCache:
    """Simple file-based cache with time-to-live."""

    def __init__(self, cache_dir: str = ".cache", default_ttl: int = 3600):
        """
        Initialize cache.

        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live in seconds
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            # Check if expired
            if time.time() > data['expires_at']:
                cache_file.unlink()  # Delete expired
                return None

            return data['value']
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with TTL."""
        if ttl is None:
            ttl = self.default_ttl

        cache_file = self.cache_dir / f"{self._hash_key(key)}.json"

        try:
            data = {
                'value': value,
                'expires_at': time.time() + ttl,
                'key': key
            }

            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass  # Silently fail caching

    def _hash_key(self, key: str) -> str:
        """Create safe filename from key."""
        import hashlib
        return hashlib.md5(key.encode()).hexdigest()

    def clear(self):
        """Clear all cache files."""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except Exception:
                pass


# Global cache instance
_cache = SimpleCache()


def get_cache(key: str) -> Optional[Any]:
    """Get value from global cache."""
    return _cache.get(key)


def set_cache(key: str, value: Any, ttl: Optional[int] = None):
    """Set value in global cache."""
    _cache.set(key, value, ttl)


def clear_cache():
    """Clear global cache."""
    _cache.clear()
