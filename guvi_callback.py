import httpx
import requests
import logging
from config import GUVI_CALLBACK_URL
from session_manager import SessionData

logger = logging.getLogger(__name__)


def send_callback_to_guvi(session: SessionData) -> bool:
    """
    Send intelligence to GUVI evaluation endpoint (synchronous version).
    Used by the cleanup thread where async is not available.
    Returns True if successful, False otherwise.
    """
    payload = _build_payload(session)
    
    try:
        logger.info(f"Sending callback to GUVI for session {session.session_id}")
        logger.info(f"Payload: {payload}")
        
        response = requests.post(
            GUVI_CALLBACK_URL,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            logger.info(f"GUVI callback successful for session {session.session_id}")
            return True
        else:
            logger.warning(f"GUVI callback returned status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"GUVI callback timeout for session {session.session_id}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"GUVI callback error for session {session.session_id}: {e}")
        return False


async def send_callback_async(session: SessionData) -> bool:
    """
    Send callback asynchronously using httpx (non-blocking).
    Preferred for use within async FastAPI endpoints.
    """
    payload = _build_payload(session)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                GUVI_CALLBACK_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"Async GUVI callback successful for session {session.session_id}")
                return True
            else:
                logger.warning(f"Async GUVI callback returned {response.status_code}: {response.text}")
                return False
                
    except httpx.TimeoutException:
        logger.error(f"Async GUVI callback timeout for session {session.session_id}")
        return False
    except Exception as e:
        logger.error(f"Async GUVI callback error for session {session.session_id}: {e}")
        return False


def send_callback_background(session: SessionData):
    """
    Send callback in background thread (non-blocking, synchronous HTTP).
    Used when async context is not available or as fallback.
    """
    import threading
    
    def _send():
        send_callback_to_guvi(session)
    
    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()


def _build_payload(session: SessionData) -> dict:
    """Build the callback payload from session data."""
    payload = {
        "sessionId": session.session_id,
        "scamDetected": session.scam_detected,
        "totalMessagesExchanged": session.message_count,
        "extractedIntelligence": {
            "bankAccounts": session.intelligence.bankAccounts,
            "upiIds": session.intelligence.upiIds,
            "phishingLinks": session.intelligence.phishingLinks,
            "phoneNumbers": session.intelligence.phoneNumbers,
            "suspiciousKeywords": session.intelligence.suspiciousKeywords,
            "paymentApps": session.intelligence.paymentApps,
            "domainRiskScores": session.intelligence.domainRiskScores,
        },
        "agentNotes": session.get_notes_string()
    }
    
    # Add emotional state if available
    if hasattr(session, 'emotional_state') and session.emotional_state:
        payload["emotionalProfile"] = session.emotional_state.to_dict()
    
    return payload
