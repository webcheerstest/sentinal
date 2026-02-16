"""
In-memory rate limiter with sliding window counters.
Per-session, per-IP, and global LLM call limits.
Thread-safe and lightweight for 1 CPU / 4GB RAM VPS.
"""
import time
import threading
from typing import Tuple
from collections import defaultdict


class RateLimiter:
    """Thread-safe sliding window rate limiter."""
    
    def __init__(self):
        self._lock = threading.Lock()
        
        # Per-session: max messages
        self._session_counts: dict = {}  # session_id -> message_count
        self.SESSION_MAX = 50
        
        # Per-IP: sliding window
        self._ip_windows: dict = defaultdict(list)  # ip -> [timestamps]
        self.IP_MAX = 100
        self.IP_WINDOW_SECONDS = 600  # 10 minutes
        
        # Global LLM calls: sliding window
        self._llm_calls: list = []
        self.LLM_MAX = 30
        self.LLM_WINDOW_SECONDS = 300  # 5 minutes
    
    def check_session(self, session_id: str) -> Tuple[bool, str]:
        """Check if session is within message limit."""
        with self._lock:
            count = self._session_counts.get(session_id, 0)
            if count >= self.SESSION_MAX:
                return False, f"Session message limit reached ({self.SESSION_MAX} messages)"
            return True, ""
    
    def increment_session(self, session_id: str):
        """Increment session message count."""
        with self._lock:
            self._session_counts[session_id] = self._session_counts.get(session_id, 0) + 1
    
    def check_ip(self, ip: str) -> Tuple[bool, str]:
        """Check if IP is within rate limit using sliding window."""
        now = time.time()
        with self._lock:
            # Clean old entries
            cutoff = now - self.IP_WINDOW_SECONDS
            self._ip_windows[ip] = [t for t in self._ip_windows[ip] if t > cutoff]
            
            if len(self._ip_windows[ip]) >= self.IP_MAX:
                return False, f"IP rate limit exceeded ({self.IP_MAX} requests per {self.IP_WINDOW_SECONDS // 60} minutes)"
            return True, ""
    
    def record_ip(self, ip: str):
        """Record an IP request."""
        with self._lock:
            self._ip_windows[ip].append(time.time())
    
    def check_llm(self) -> Tuple[bool, str]:
        """Check if global LLM call limit allows another call."""
        now = time.time()
        with self._lock:
            cutoff = now - self.LLM_WINDOW_SECONDS
            self._llm_calls = [t for t in self._llm_calls if t > cutoff]
            
            if len(self._llm_calls) >= self.LLM_MAX:
                return False, f"LLM rate limit exceeded ({self.LLM_MAX} calls per {self.LLM_WINDOW_SECONDS // 60} minutes)"
            return True, ""
    
    def record_llm_call(self):
        """Record an LLM API call."""
        with self._lock:
            self._llm_calls.append(time.time())
    
    def check_all(self, session_id: str, ip: str) -> Tuple[bool, str]:
        """Check all rate limits. Returns (allowed, reason)."""
        ok, reason = self.check_session(session_id)
        if not ok:
            return False, reason
        
        ok, reason = self.check_ip(ip)
        if not ok:
            return False, reason
        
        return True, ""
    
    def get_stats(self) -> dict:
        """Return rate limiter statistics."""
        now = time.time()
        with self._lock:
            active_sessions = len(self._session_counts)
            active_ips = len(self._ip_windows)
            llm_cutoff = now - self.LLM_WINDOW_SECONDS
            recent_llm = len([t for t in self._llm_calls if t > llm_cutoff])
        
        return {
            "active_sessions_tracked": active_sessions,
            "active_ips_tracked": active_ips,
            "llm_calls_in_window": recent_llm,
            "llm_limit": self.LLM_MAX
        }


# Global instance
rate_limiter = RateLimiter()
