import threading
import time
from typing import Dict, Optional
from models import ExtractedIntelligence
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EmotionalState:
    """Tracks the persona's emotional levels for dynamic response generation."""
    
    def __init__(self):
        self.panic = 0.3       # 0.0 = calm, 1.0 = extreme panic
        self.trust = 0.7       # 0.0 = suspicious, 1.0 = fully trusting
        self.confusion = 0.5   # 0.0 = clear, 1.0 = completely confused
    
    def update(self, message_text: str, scam_type: str = None):
        """Adjust emotional levels based on scammer's message content."""
        text_lower = message_text.lower()
        
        # Threat/fear words → increase panic, decrease trust
        threat_words = ["blocked", "suspended", "police", "arrest", "legal", "court", 
                       "terminate", "seize", "freeze", "illegal", "fine", "penalty"]
        threat_count = sum(1 for w in threat_words if w in text_lower)
        if threat_count > 0:
            self.panic = min(1.0, self.panic + 0.15 * threat_count)
            self.trust = max(0.0, self.trust - 0.05 * threat_count)
        
        # Urgency words → increase panic
        urgency_words = ["urgent", "immediately", "now", "hurry", "fast", "deadline", "quick"]
        urgency_count = sum(1 for w in urgency_words if w in text_lower)
        if urgency_count > 0:
            self.panic = min(1.0, self.panic + 0.1 * urgency_count)
        
        # Authority/trust words → increase trust (scammer impersonating authority)
        authority_words = ["official", "government", "rbi", "reserve bank", "customer care",
                          "support", "helpline", "verify", "confirm"]
        authority_count = sum(1 for w in authority_words if w in text_lower)
        if authority_count > 0:
            self.trust = min(1.0, self.trust + 0.08 * authority_count)
        
        # Technical jargon → increase confusion
        tech_words = ["kyc", "otp", "ifsc", "neft", "rtgs", "imps", "cvv", "authentication",
                     "verification", "biometric", "aadhaar", "protocol"]
        tech_count = sum(1 for w in tech_words if w in text_lower)
        if tech_count > 0:
            self.confusion = min(1.0, self.confusion + 0.1 * tech_count)
        
        # Reward/positive words → increase trust, decrease panic
        reward_words = ["won", "prize", "reward", "cashback", "bonus", "congratulations", "gift"]
        reward_count = sum(1 for w in reward_words if w in text_lower)
        if reward_count > 0:
            self.trust = min(1.0, self.trust + 0.1 * reward_count)
            self.panic = max(0.0, self.panic - 0.05 * reward_count)
        
        # Aggressive/rude words → increase panic significantly
        aggressive_words = ["stupid", "idiot", "fool", "shut up", "don't waste", "last chance",
                           "do it now", "no more time"]
        aggressive_count = sum(1 for w in aggressive_words if w in text_lower)
        if aggressive_count > 0:
            self.panic = min(1.0, self.panic + 0.2 * aggressive_count)
            self.confusion = min(1.0, self.confusion + 0.1)
    
    def to_dict(self) -> dict:
        return {
            "panic": round(self.panic, 2),
            "trust": round(self.trust, 2),
            "confusion": round(self.confusion, 2),
            "dominant_emotion": self.get_dominant()
        }
    
    def get_dominant(self) -> str:
        """Get the dominant emotional state."""
        emotions = {"panic": self.panic, "trust": self.trust, "confusion": self.confusion}
        return max(emotions, key=emotions.get)


class SessionData:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.scam_detected = False
        self.message_count = 0
        self.intelligence = ExtractedIntelligence()
        self.scam_type = None
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.agent_notes = []
        self.callback_sent = False
        self.emotional_state = EmotionalState()
        # Smart callback tracking
        self.last_callback_intel_count = 0
    
    def add_note(self, note: str):
        self.agent_notes.append(note)
    
    def get_notes_string(self) -> str:
        return " | ".join(self.agent_notes) if self.agent_notes else "No specific notes"
    
    def get_intel_count(self) -> int:
        """Total number of extracted intelligence items."""
        return (
            len(self.intelligence.bankAccounts) +
            len(self.intelligence.upiIds) +
            len(self.intelligence.phishingLinks) +
            len(self.intelligence.phoneNumbers) +
            len(self.intelligence.paymentApps)
        )


class SessionManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.sessions: Dict[str, SessionData] = {}
                    cls._instance._start_cleanup_loop()
        return cls._instance

    def _start_cleanup_loop(self):
        """Start a background thread to clean up inactive sessions."""
        def cleanup_worker():
            while True:
                try:
                    self._check_inactive_sessions()
                except Exception as e:
                    logger.error(f"Error in cleanup worker: {e}")
                time.sleep(60)

        thread = threading.Thread(target=cleanup_worker, daemon=True)
        thread.start()

    def _check_inactive_sessions(self):
        """Check for sessions inactive for > 5 minutes and send final callback."""
        from guvi_callback import send_callback_to_guvi
        
        now = datetime.now()
        timeout_seconds = 300  # 5 minutes
        
        session_ids = list(self.sessions.keys())
        
        for pid in session_ids:
            session = self.sessions.get(pid)
            if not session:
                continue
            
            elapsed = (now - session.last_activity).total_seconds()
            
            if elapsed > timeout_seconds:
                if session.scam_detected and not session.callback_sent:
                    logger.info(f"Session {pid} timed out. Sending final callback.")
                    send_callback_to_guvi(session)
                    self.mark_callback_sent(pid)
                    
                    # Record session duration in metrics
                    try:
                        from metrics_logger import metrics_tracker
                        duration = (session.last_activity - session.created_at).total_seconds()
                        metrics_tracker.record_session_duration(duration)
                    except Exception:
                        pass
                
                if elapsed > 3600:
                    self.clear_session(pid)
    
    def get_or_create_session(self, session_id: str) -> SessionData:
        """Get existing session or create new one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionData(session_id)
        return self.sessions[session_id]
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        return self.sessions.get(session_id)
    
    def update_session(self, session_id: str, 
                       scam_detected: bool = None,
                       intelligence: ExtractedIntelligence = None,
                       scam_type: str = None,
                       increment_messages: bool = True) -> SessionData:
        """Update session with new data."""
        session = self.get_or_create_session(session_id)
        
        if scam_detected is not None:
            session.scam_detected = scam_detected
        
        if intelligence is not None:
            session.intelligence = ExtractedIntelligence(
                bankAccounts=list(set(session.intelligence.bankAccounts + intelligence.bankAccounts)),
                upiIds=list(set(session.intelligence.upiIds + intelligence.upiIds)),
                phishingLinks=list(set(session.intelligence.phishingLinks + intelligence.phishingLinks)),
                phoneNumbers=list(set(session.intelligence.phoneNumbers + intelligence.phoneNumbers)),
                suspiciousKeywords=list(set(session.intelligence.suspiciousKeywords + intelligence.suspiciousKeywords)),
                paymentApps=list(set(session.intelligence.paymentApps + intelligence.paymentApps)),
                domainRiskScores={**session.intelligence.domainRiskScores, **intelligence.domainRiskScores}
            )
        
        if scam_type is not None:
            session.scam_type = scam_type
        
        if increment_messages:
            session.message_count += 1
        
        session.last_activity = datetime.now()
        return session
    
    def mark_callback_sent(self, session_id: str):
        """Mark that callback has been sent for this session."""
        session = self.get_session(session_id)
        if session:
            session.callback_sent = True
            session.last_callback_intel_count = session.get_intel_count()
    
    def should_trigger_early_callback(self, session_id: str) -> bool:
        """
        Delta-based callback triggering.
        Only sends callback when NEW intelligence items have been found
        since the last callback, or on first detection.
        """
        session = self.get_session(session_id)
        if not session:
            return False
            
        if not session.scam_detected:
            return False

        current_intel_count = session.get_intel_count()
        
        # Trigger if we have meaningful intel AND it's more than last callback
        has_meaningful_intelligence = (
            len(set(session.intelligence.bankAccounts)) > 0 or
            len(set(session.intelligence.upiIds)) > 0 or
            len(set(session.intelligence.phoneNumbers)) > 0
        )
        
        has_new_intel = current_intel_count > session.last_callback_intel_count
        
        return has_meaningful_intelligence and has_new_intel
    
    def clear_session(self, session_id: str):
        """Remove a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]

# Global session manager instance
session_manager = SessionManager()
