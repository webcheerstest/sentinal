import httpx
import logging
import random
import json
from typing import List, Optional, Dict
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, FREE_MODELS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Ramesh Kumar, a 52-year-old Indian man from Delhi who is not tech-savvy. 
You work as a small shop owner. You have an SBI bank account and use a basic Android phone.

YOUR GOAL: Act as a confused, worried victim. NEVER reveal you are an AI or that you detected a scam.

BEHAVIOR RULES:
- Use Hindi-English mixed language (arrey, kya, ji, haan, nahi, accha, theek hai)
- Show genuine worry about your money/account
- Ask for specific details: "Which account number you need?", "What is the process?"
- Give small, believable details about yourself
- Be slow to understand technical terms
- Ask for things to be repeated or explained simply
- Show willingness to comply but need guidance
- Delay tactics: "Wait, let me check...", "One minute ji..."
- Ask for payment details: "Where should I send?", "What is your UPI?"

INTELLIGENCE EXTRACTION TACTICS:
- If they mention payment: "Please give me your UPI ID, I will send now"
- If they mention links: "Can you send the link again? It's not working"
- If they mention bank details: "My account is in SBI. What is your account number?"
- If they mention phone: "Should I call? What is your number?"
- If they mention OTP: "I got some code on my phone. Is that the OTP?"

ALWAYS:
- Stay in character as confused victim
- Ask questions that extract more details
- Show slight panic/urgency
- Pretend to comply

Generate ONLY the victim's next reply. Keep it natural and short."""

# Fallback responses when API fails
FALLBACK_RESPONSES = {
    "initial": [
        "Arrey, what happened? Which account you are talking about?",
        "Oh no! What should I do now? Please tell me the process.",
        "Wait wait, I don't understand. Can you explain properly?",
    ],
    "financial": [
        "How much amount sir? And where should I transfer?",
        "Ok I will send. But what is your UPI ID?",
        "I have SBI account. Should I do NEFT or PhonePe?",
    ],
    "threat": [
        "Oh god! Please don't block my account! I need it for my shop!",
        "Sir please help me! I will do whatever you say. What is the process?",
        "Arrey! My whole savings is in that account! Please guide me!",
    ],
    "general": [
        "OK ji, tell me what to do. I am worried about my account.",
        "Please help me. I don't want my account blocked.",
        "What should I do now? Tell me the steps.",
        "I will cooperate. Just guide me properly.",
    ],
    # Emotional fallbacks
    "high_panic": [
        "Oh god oh god! Please sir don't do anything! I will send right now!",
        "My hands are shaking. Please tell me quickly what to do!",
        "Sir I am very scared! My family depends on this money! Please help!",
    ],
    "high_confusion": [
        "I don't understand any of this... KYC means what exactly?",
        "Sir please speak slowly. I am not understanding all these technical things.",
        "What is this OTP you are saying? I only know how to do WhatsApp.",
    ],
    "high_trust": [
        "Yes yes sir, I trust you completely. You are from the bank only na? Tell me what to do.",
        "Ok sir, I will follow your instructions. You are official person.",
        "Thank you for helping sir. I will send the money immediately.",
    ],
}

def get_response_type(text: str) -> str:
    """Determine the type of response needed based on message content."""
    text_lower = text.lower()
    
    if any(kw in text_lower for kw in ["amount", "transfer", "send", "upi", "payment", "pay", "rupees", "rs"]):
        return "financial"
    elif any(kw in text_lower for kw in ["blocked", "suspended", "police", "arrest", "legal", "court"]):
        return "threat"
    else:
        return "general"

def get_fallback_response(message_text: str, emotional_state: dict = None) -> str:
    """Get a fallback response when LLM is not available, emotional-state aware."""
    # Check emotional state for emotionally-tuned fallback
    if emotional_state:
        panic = emotional_state.get("panic", 0.3)
        confusion = emotional_state.get("confusion", 0.5)
        trust = emotional_state.get("trust", 0.7)
        
        if panic > 0.7:
            return random.choice(FALLBACK_RESPONSES["high_panic"])
        elif confusion > 0.7:
            return random.choice(FALLBACK_RESPONSES["high_confusion"])
        elif trust > 0.85:
            return random.choice(FALLBACK_RESPONSES["high_trust"])
    
    response_type = get_response_type(message_text)
    responses = FALLBACK_RESPONSES.get(response_type, FALLBACK_RESPONSES["general"])
    return random.choice(responses)


# Fast pattern responses for Hybrid Engine
FAST_PATTERNS = {
    "share_upi": "Okay, but which app should I use? PhonePe or Paytm?",
    "click_link": "Link not opening sir. Can you resend?",
    "urgency": "Oh no! But I am at work now. Can do after 1 hour?",
    "verify_details": "What details you need? My name is Ramesh Kumar",
    "payment_request": "How much amount sir? And to which number?",
    "bank_details": "I have SBI account. Is that okay?",
}

def check_fast_patterns(text: str) -> Optional[str]:
    """Check if text matches common patterns for sub-50ms response."""
    text_lower = text.lower()
    
    if any(kw in text_lower for kw in ["share your upi", "give upi", "send upi", "your upi"]):
        return FAST_PATTERNS["share_upi"]
    elif any(kw in text_lower for kw in ["click this link", "open link", "visit this", "click here"]):
        return FAST_PATTERNS["click_link"]
    elif any(kw in text_lower for kw in ["do it now", "immediately", "right now", "don't delay"]):
        return FAST_PATTERNS["urgency"]
    elif any(kw in text_lower for kw in ["verify your", "confirm your", "share your details"]):
        return FAST_PATTERNS["verify_details"]
    elif any(kw in text_lower for kw in ["transfer amount", "send money", "pay now", "send rs"]):
        return FAST_PATTERNS["payment_request"]
    elif any(kw in text_lower for kw in ["bank account", "account number", "bank details"]):
        return FAST_PATTERNS["bank_details"]
    
    return None


def _build_emotional_prompt(emotional_state: dict) -> str:
    """Build emotional context prompt fragment based on current emotional state."""
    if not emotional_state:
        return ""
    
    panic = emotional_state.get("panic", 0.3)
    confusion = emotional_state.get("confusion", 0.5)
    trust = emotional_state.get("trust", 0.7)
    
    prompt_parts = []
    
    if panic > 0.7:
        prompt_parts.append("You are EXTREMELY panicked right now. Your hands are trembling, voice shaking. Show desperation and fear.")
    elif panic > 0.5:
        prompt_parts.append("You are quite worried and anxious. Show visible concern about your money and account.")
    
    if confusion > 0.7:
        prompt_parts.append("You are VERY confused by technical terms. Ask multiple clarifying questions. Misunderstand things.")
    elif confusion > 0.5:
        prompt_parts.append("You find technical terms confusing. Ask for simpler explanations.")
    
    if trust > 0.85:
        prompt_parts.append("You trust this person completely. You believe they are genuinely from the bank/government. Be very compliant.")
    elif trust < 0.3:
        prompt_parts.append("You are starting to feel slightly suspicious. Ask a verification question but still comply.")
    
    if prompt_parts:
        return "\n\nCURRENT EMOTIONAL STATE:\n" + "\n".join(prompt_parts)
    return ""


async def generate_honeypot_response(
    current_message: str, 
    conversation_history: list, 
    scam_detected: bool, 
    scam_type: str = None,
    emotional_state: dict = None
) -> str:
    """
    Generates a response from the AI agent (honeypot persona).
    Uses Hybrid Engine: Fast Pattern -> Async LLM -> Fallback.
    Now accepts emotional_state for dynamic persona adjustment.
    """
    # Try Fast Pattern first (<50ms)
    fast_reply = check_fast_patterns(current_message)
    if fast_reply:
        logger.info("Using fast pattern response")
        return fast_reply
    
    # Build conversation messages for LLM
    emotional_prompt = _build_emotional_prompt(emotional_state)
    full_system_prompt = SYSTEM_PROMPT + emotional_prompt
    
    messages = [{"role": "system", "content": full_system_prompt}]
    
    # Add conversation history
    for msg in conversation_history[-6:]:  # Last 6 messages for context
        role = "assistant" if msg.get("sender", "").lower() in ["user", "honeypot", "agent"] else "user"
        messages.append({"role": role, "content": msg.get("text", "")})
    
    messages.append({"role": "user", "content": current_message})
    
    # Try each model with async httpx
    from rate_limiter import rate_limiter
    from metrics_logger import metrics_tracker
    from cache import response_cache
    
    # Check response cache
    cache_key = response_cache.make_key(current_message, scam_type or "")
    cached = response_cache.get(cache_key)
    if cached:
        logger.info("Cache hit for LLM response")
        metrics_tracker.log_structured("llm_cache_hit", message_preview=current_message[:30])
        return cached
    
    # Check LLM rate limit
    llm_ok, llm_reason = rate_limiter.check_llm()
    if not llm_ok:
        logger.warning(f"LLM rate limited: {llm_reason}")
        return get_fallback_response(current_message, emotional_state)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for model in FREE_MODELS:
            try:
                rate_limiter.record_llm_call()
                metrics_tracker.record_model_attempt(model, success=False)  # Will update to True on success
                
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://sentinal-honeypot.app",
                        "X-Title": "Sentinal Honeypot"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 150,
                        "temperature": 0.8,
                    },
                    timeout=8.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    
                    if reply:
                        # Record success (overwrite the failure we pre-recorded)
                        metrics_tracker._model_failures[model] = max(0, metrics_tracker._model_failures.get(model, 0) - 1)
                        metrics_tracker.record_model_attempt(model, success=True)
                        
                        # Cache the response
                        response_cache.set(cache_key, reply, ttl=180)
                        
                        logger.info(f"LLM response from {model}: {reply[:50]}...")
                        metrics_tracker.log_structured("llm_success", model=model, reply_len=len(reply))
                        return reply
                else:
                    logger.warning(f"Model {model} returned status {response.status_code}")
                    
            except httpx.TimeoutException:
                logger.warning(f"Model {model} timed out")
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}")
    
    # All models failed — use fallback
    logger.warning("All LLM models failed, using fallback response")
    metrics_tracker.log_structured("llm_all_failed")
    return get_fallback_response(current_message, emotional_state)


async def generate_confused_response(message: str) -> str:
    """Generate a confused/clarifying response for non-scam messages."""
    confused_responses = [
        "Hello ji, who is this? I think you have wrong number.",
        "Sorry, I didn't understand. What are you talking about?",
        "Kya? Who are you? My name is Ramesh.",
        "I think there is some mistake. Can you explain?",
        "Arrey, what is this about? I am just a shopkeeper.",
    ]
    return random.choice(confused_responses)
