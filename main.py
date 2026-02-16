from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import json
import time

from config import MY_API_KEY
from models import AnalyzeRequest, AnalyzeResponse, ExtractedIntelligence
from scam_detector import detect_scam, get_scam_type, calculate_confidence
from intelligence import extract_all_intelligence, extract_from_conversation
from agent_persona import generate_honeypot_response, generate_confused_response
from session_manager import session_manager
from guvi_callback import send_callback_async, send_callback_to_guvi
from scammer_dna import ScammerDNA
from engagement_metrics import engagement_tracker
from rate_limiter import rate_limiter
from metrics_logger import metrics_tracker
from cache import detection_cache

# Configure structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Sentinal - AI Honeypot Agent",
    description="AI-powered honeypot for scam detection, intelligence extraction, and scammer engagement",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Log startup banner with system info."""
    logger.info("=" * 60)
    logger.info("  SENTINAL v2.0 - AI Honeypot Agent")
    logger.info("  Scam Detection | Intelligence Extraction | DNA Clustering")
    logger.info("=" * 60)
    metrics_tracker.log_structured("server_startup", version="2.0.0")


@app.get("/")
async def root():
    """Root endpoint - status check."""
    return {"status": "ok", "message": "Sentinal Honeypot API v2.0 is running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": int(time.time() * 1000),
        "version": "2.0.0",
        "active_sessions": len(session_manager.sessions)
    }


@app.get("/metrics")
async def get_metrics():
    """Observability metrics endpoint."""
    return {
        "system": metrics_tracker.get_metrics(),
        "rate_limiter": rate_limiter.get_stats(),
        "detection_cache": detection_cache.get_stats(),
        "dna_clusters": ScammerDNA().get_cluster_stats()
    }


@app.post("/analyze")
@app.post("/api/analyze")
async def analyze_message(
    request: Request,
    request_body: AnalyzeRequest,
    x_api_key: str = Header(None, alias="x-api-key")
):
    """
    Main endpoint to analyze incoming messages.
    Detects scams, engages with honeypot persona, extracts intelligence.
    """
    start_time = time.time()
    
    # Validate API key
    if x_api_key != MY_API_KEY:
        logger.warning(f"Invalid API key attempt: {x_api_key}")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Extract client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    session_id = request_body.sessionId
    
    # === RATE LIMITING ===
    allowed, reason = rate_limiter.check_all(session_id, client_ip)
    if not allowed:
        metrics_tracker.log_structured("rate_limited", session_id=session_id, reason=reason)
        raise HTTPException(status_code=429, detail=reason)
    
    rate_limiter.increment_session(session_id)
    rate_limiter.record_ip(client_ip)
    
    try:
        # Extract fields
        message_text = request_body.message.text
        conversation_history_objs = request_body.conversationHistory or []
        
        conversation_history = [
            {"sender": m.sender, "text": m.text, "timestamp": m.timestamp}
            for m in conversation_history_objs
        ]
        
        logger.info(f"Processing message for session {session_id}")
        
        # Get or create session
        session = session_manager.get_or_create_session(session_id)
        
        # === SCAM DETECTION (with caching) ===
        det_cache_key = detection_cache.make_key(message_text)
        cached_detection = detection_cache.get(det_cache_key)
        
        if cached_detection:
            scam_detected, keywords, scam_score, categories_hit = cached_detection
            cache_hit = True
        else:
            scam_detected, keywords, scam_score, categories_hit = detect_scam(message_text, conversation_history)
            detection_cache.set(det_cache_key, (scam_detected, keywords, scam_score, categories_hit))
            cache_hit = False
        
        scam_type = get_scam_type(keywords) if scam_detected else None
        
        # === CONFIDENCE CALIBRATION ===
        confidence = calculate_confidence(
            scam_score=scam_score,
            keyword_count=len(keywords),
            categories_hit=categories_hit,
            history_len=len(conversation_history)
        )
        
        # === INTELLIGENCE EXTRACTION ===
        def get_message_text(msg) -> str:
            if isinstance(msg, str):
                return msg
            if isinstance(msg, dict):
                for field in ['text', 'content', 'body', 'message']:
                    if field in msg and msg[field]:
                        val = msg[field]
                        if isinstance(val, str):
                            return val
                        elif isinstance(val, dict):
                            return get_message_text(val)
            return ""
        
        all_texts = [message_text]
        for msg in conversation_history:
            msg_text = get_message_text(msg)
            if msg_text:
                all_texts.append(msg_text)
        
        combined_text = "\n".join(all_texts)
        current_intel = extract_all_intelligence(combined_text)
        
        # === UPDATE SESSION ===
        session = session_manager.update_session(
            session_id=session_id,
            scam_detected=scam_detected or session.scam_detected,
            intelligence=current_intel,
            scam_type=scam_type or session.scam_type,
            increment_messages=True
        )
        
        # Add agent notes
        if scam_detected and session.message_count <= 2:
            session.add_note(f"Scam detected: {scam_type}")
        if keywords:
            session.add_note(f"Keywords: {', '.join(keywords[:5])}")
        
        # === EMOTIONAL STATE UPDATE ===
        session.emotional_state.update(message_text, session.scam_type)
        emotional_dict = session.emotional_state.to_dict()
        
        # === ENGAGEMENT TRACKING ===
        new_intel_count = (
            len(current_intel.bankAccounts) + 
            len(current_intel.upiIds) + 
            len(current_intel.phishingLinks) + 
            len(current_intel.phoneNumbers) +
            len(current_intel.paymentApps)
        )
        engagement_tracker.update(session_id, request_body.message.sender, new_intel_count)
        
        # === SCAMMER DNA FINGERPRINTING ===
        dna_engine = ScammerDNA()
        full_dna_history = conversation_history.copy()
        full_dna_history.append({
            "sender": request_body.message.sender,
            "text": request_body.message.text,
            "timestamp": request_body.message.timestamp
        })
        
        signature, features = dna_engine.generate_fingerprint_from_history(full_dna_history, session_id)
        
        # Record scam in metrics
        if scam_detected and session.scam_type:
            metrics_tracker.record_scam(session.scam_type)
        
        # === GENERATE RESPONSE (Async LLM) ===
        if session.scam_detected:
            reply = await generate_honeypot_response(
                current_message=message_text,
                conversation_history=conversation_history,
                scam_detected=True,
                scam_type=session.scam_type,
                emotional_state=emotional_dict
            )
        else:
            reply = await generate_confused_response(message_text)
            
        logger.info(f"Generated reply for session {session_id}: {reply[:50]}...")
        
        # === SMART CALLBACK (Delta-based) ===
        if session_manager.should_trigger_early_callback(session_id):
            logger.info(f"Smart Trigger: Sending callback for session {session_id} (new intel found)")
            await send_callback_async(session)
            session_manager.mark_callback_sent(session_id)
        
        # === BUILD RESPONSE ===
        processing_time = int((time.time() - start_time) * 1000)
        
        response = AnalyzeResponse(
            status="success",
            reply=reply,
            scamDetected=session.scam_detected,
            extractedIntelligence=session.intelligence,
            scamAnalysis={
                "detected": session.scam_detected,
                "type": session.scam_type or "unknown",
                "confidence": confidence,
                "scam_score": scam_score,
                "categories_hit": list(categories_hit.keys()),
                "processing_time_ms": processing_time,
                "cache_hit": cache_hit
            },
            scammerProfile={
                "behavioral_signature": signature,
                "tactics": features.get('tactics', []),
                "timing_pattern": features.get('timing', 'unknown'),
                "structure": features.get('structure', 'unknown'),
                "repeat_scammer": features.get('repeat_scammer', False),
                "cluster_label": features.get('cluster_label', 'New Pattern'),
                "similarity_score": features.get('similarity_score', 0.0),
                "known_patterns": features.get('known_patterns_count', 0),
            },
            engagementMetrics=engagement_tracker.calculate_impact(session_id),
            systemStatus={
                "active_sessions": len(session_manager.sessions),
                "optimization_level": "production",
                "emotional_state": emotional_dict,
                "version": "2.0.0"
            }
        )
        
        # Record request metrics
        metrics_tracker.record_request(processing_time)
        metrics_tracker.log_structured(
            "analyze_complete",
            session_id=session_id,
            scam_detected=session.scam_detected,
            confidence=confidence,
            scam_type=session.scam_type,
            intel_count=session.get_intel_count(),
            processing_ms=processing_time,
            cache_hit=cache_hit
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error processing request: {e}")
        logger.error(traceback.format_exc())
        metrics_tracker.log_structured("analyze_error", error=str(e), session_id=session_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "reply": "Sorry, I didn't understand. Can you explain again?",
                "scamDetected": False
            }
        )


@app.post("/debug/session/{session_id}")
async def get_session_debug(
    session_id: str,
    x_api_key: str = Header(None, alias="x-api-key")
):
    """Debug endpoint to view session state."""
    if x_api_key != MY_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {
        "session_id": session.session_id,
        "scam_detected": session.scam_detected,
        "scam_type": session.scam_type,
        "message_count": session.message_count,
        "intelligence": session.intelligence,
        "callback_sent": session.callback_sent,
        "notes": session.agent_notes,
        "emotional_state": session.emotional_state.to_dict(),
        "intel_count": session.get_intel_count(),
        "last_callback_intel_count": session.last_callback_intel_count,
    }


@app.post("/callback/force/{session_id}")
async def force_callback(
    session_id: str,
    x_api_key: str = Header(None, alias="x-api-key")
):
    """Force trigger callback for a session."""
    if x_api_key != MY_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    success = await send_callback_async(session)
    session_manager.mark_callback_sent(session_id)
    
    return {"status": "success", "callback_triggered": True, "guvi_response": success}
