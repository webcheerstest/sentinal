"""
Structured metrics tracking and logging for observability.
Tracks scam type frequency, session durations, model failures, and cache stats.
"""
import time
import threading
import json
import logging
from collections import defaultdict
from typing import Dict, Any


logger = logging.getLogger(__name__)


class MetricsTracker:
    """Thread-safe metrics aggregator for system observability."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()
        
        # Scam type frequency
        self._scam_type_counts: Dict[str, int] = defaultdict(int)
        
        # Session durations (completed sessions)
        self._session_durations: list = []
        
        # Model usage and failures
        self._model_attempts: Dict[str, int] = defaultdict(int)
        self._model_failures: Dict[str, int] = defaultdict(int)
        self._model_successes: Dict[str, int] = defaultdict(int)
        
        # Request metrics
        self._total_requests = 0
        self._total_scams_detected = 0
        self._response_times: list = []  # last 100
    
    def record_request(self, response_time_ms: float):
        """Record a request with its response time."""
        with self._lock:
            self._total_requests += 1
            self._response_times.append(response_time_ms)
            if len(self._response_times) > 100:
                self._response_times = self._response_times[-100:]
    
    def record_scam(self, scam_type: str):
        """Record a detected scam type."""
        with self._lock:
            self._scam_type_counts[scam_type] += 1
            self._total_scams_detected += 1
    
    def record_model_attempt(self, model_name: str, success: bool):
        """Record an LLM model attempt."""
        with self._lock:
            self._model_attempts[model_name] += 1
            if success:
                self._model_successes[model_name] += 1
            else:
                self._model_failures[model_name] += 1
    
    def record_session_duration(self, duration_seconds: float):
        """Record the duration of a completed session."""
        with self._lock:
            self._session_durations.append(duration_seconds)
            if len(self._session_durations) > 500:
                self._session_durations = self._session_durations[-500:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics snapshot."""
        with self._lock:
            uptime = time.time() - self._start_time
            
            # Average response time
            avg_response = (
                round(sum(self._response_times) / len(self._response_times), 2)
                if self._response_times else 0
            )
            
            # Average session duration
            avg_session = (
                round(sum(self._session_durations) / len(self._session_durations), 1)
                if self._session_durations else 0
            )
            
            # Model failure rates
            model_stats = {}
            for model in set(list(self._model_attempts.keys())):
                attempts = self._model_attempts[model]
                failures = self._model_failures.get(model, 0)
                model_stats[model] = {
                    "attempts": attempts,
                    "failures": failures,
                    "failure_rate": round(failures / attempts, 3) if attempts > 0 else 0
                }
            
            return {
                "uptime_seconds": int(uptime),
                "total_requests": self._total_requests,
                "total_scams_detected": self._total_scams_detected,
                "scam_type_frequency": dict(self._scam_type_counts),
                "avg_response_time_ms": avg_response,
                "avg_session_duration_s": avg_session,
                "model_performance": model_stats,
                "detection_rate": round(
                    self._total_scams_detected / self._total_requests, 3
                ) if self._total_requests > 0 else 0
            }
    
    def log_structured(self, event: str, **kwargs):
        """Emit a structured JSON log entry."""
        entry = {
            "timestamp": time.time(),
            "event": event,
            **kwargs
        }
        logger.info(json.dumps(entry))


# Global instance
metrics_tracker = MetricsTracker()
