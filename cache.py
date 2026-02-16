"""
In-memory LRU cache with TTL for detection results and LLM responses.
Optimized for 1 CPU / 4GB RAM VPS — max 200 entries.
"""
import time
import threading
import hashlib
from collections import OrderedDict
from typing import Any, Optional


class ResponseCache:
    """Thread-safe LRU cache with per-entry TTL."""
    
    def __init__(self, max_size: int = 200, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl  # 5 minutes
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0}
    
    @staticmethod
    def make_key(text: str, context: str = "") -> str:
        """Create a cache key from message text and optional context."""
        raw = f"{text.lower().strip()}|{context}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache. Returns None if missing or expired."""
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            
            value, expiry = self._cache[key]
            if time.time() > expiry:
                # Expired — remove it
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return value
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache with optional custom TTL."""
        ttl = ttl or self.default_ttl
        expiry = time.time() + ttl
        
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, expiry)
            
            # Evict oldest if over capacity
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
    
    def get_stats(self) -> dict:
        """Return cache hit/miss statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": round(self._stats["hits"] / total, 3) if total > 0 else 0.0,
            "size": len(self._cache),
            "max_size": self.max_size
        }
    
    def clear(self):
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()


# Global cache instances
detection_cache = ResponseCache(max_size=200, default_ttl=300)
response_cache = ResponseCache(max_size=100, default_ttl=180)
