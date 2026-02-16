import re
import math
from typing import List, Tuple, Dict, Any

# Scam indicator patterns and keywords
URGENCY_KEYWORDS = [
    "urgent", "immediately", "today", "now", "quick", "fast", "hurry",
    "limited time", "expires", "deadline", "asap", "right away", "don't delay",
    "act now", "warning", "alert", "important", "critical"
]

THREAT_KEYWORDS = [
    "blocked", "suspended", "deactivated", "terminated", "closed", "frozen",
    "seized", "legal action", "police", "court", "arrest", "fine", "penalty",
    "will be blocked", "account blocked", "account suspended"
]

FINANCIAL_KEYWORDS = [
    "bank", "account", "upi", "payment", "transfer", "money", "rupees", "rs",
    "balance", "transaction", "kyc", "verify", "verification", "update",
    "otp", "pin", "cvv", "card", "atm", "ifsc", "neft", "rtgs", "imps"
]

REWARD_KEYWORDS = [
    "won", "winner", "prize", "lottery", "reward", "cashback", "bonus",
    "free", "gift", "offer", "lucky", "congratulations", "selected", "chosen"
]

IMPERSONATION_KEYWORDS = [
    "rbi", "reserve bank", "government", "ministry", "income tax", "it department",
    "sbi", "hdfc", "icici", "axis", "paytm", "phonepe", "gpay", "google pay",
    "customer care", "support", "helpline", "official"
]

ACTION_KEYWORDS = [
    "click", "link", "call", "contact", "share", "send", "provide", "enter",
    "submit", "confirm", "verify", "update", "download", "install"
]

# Category names for combo detection
CATEGORY_NAMES = {
    "urgency": URGENCY_KEYWORDS,
    "threat": THREAT_KEYWORDS,
    "financial": FINANCIAL_KEYWORDS,
    "reward": REWARD_KEYWORDS,
    "impersonation": IMPERSONATION_KEYWORDS,
    "action": ACTION_KEYWORDS,
}

# Combo bonuses: (category_a, category_b) -> bonus_score
COMBO_BONUSES = {
    ("urgency", "financial"): 3,
    ("threat", "financial"): 3,
    ("impersonation", "financial"): 2,
    ("urgency", "threat"): 2,
    ("action", "impersonation"): 2,
    ("reward", "action"): 2,
}

# Base scores per category
CATEGORY_SCORES = {
    "urgency": 2,
    "threat": 3,
    "financial": 1,
    "reward": 2,
    "impersonation": 2,
    "action": 1,
}


def detect_scam(text: str, conversation_history: List[dict] = None) -> Tuple[bool, List[str], int, Dict[str, List[str]]]:
    """
    Analyze text for scam indicators with context-aware combo scoring.
    Returns (is_scam, detected_keywords, scam_score, categories_hit)
    """
    text_lower = text.lower()
    detected_keywords = []
    scam_score = 0
    categories_hit: Dict[str, List[str]] = {}
    
    # Check each category
    for category_name, keyword_list in CATEGORY_NAMES.items():
        category_keywords = []
        for keyword in keyword_list:
            if keyword in text_lower:
                category_keywords.append(keyword)
                detected_keywords.append(keyword)
                scam_score += CATEGORY_SCORES[category_name]
        if category_keywords:
            categories_hit[category_name] = category_keywords
    
    # Check for URLs (often suspicious)
    url_pattern = r'https?://[^\s]+'
    if re.search(url_pattern, text_lower):
        detected_keywords.append("contains_url")
        scam_score += 2
        categories_hit.setdefault("action", []).append("contains_url")
    
    # Check for phone numbers
    phone_pattern = r'[\+]?[0-9]{10,12}'
    if re.search(phone_pattern, text):
        detected_keywords.append("contains_phone")
        scam_score += 1
    
    # Check for UPI ID patterns
    upi_pattern = r'[a-zA-Z0-9._-]+@[a-zA-Z]+'
    if re.search(upi_pattern, text_lower):
        detected_keywords.append("contains_upi")
        scam_score += 2
        categories_hit.setdefault("financial", []).append("contains_upi")
    
    # === COMBO SCORING ===
    # Bonus points when dangerous categories appear together
    combo_bonus = 0
    hit_names = set(categories_hit.keys())
    for (cat_a, cat_b), bonus in COMBO_BONUSES.items():
        if cat_a in hit_names and cat_b in hit_names:
            combo_bonus += bonus
    scam_score += combo_bonus
    
    # === CUMULATIVE SESSION SCORING ===
    # Analyze conversation history for building scam patterns
    if conversation_history:
        history_text = " ".join([msg.get("text", "") for msg in conversation_history])
        history_lower = history_text.lower()
        
        # Count categories present across history
        history_categories = set()
        for category_name, keyword_list in CATEGORY_NAMES.items():
            if any(kw in history_lower for kw in keyword_list):
                history_categories.add(category_name)
        
        # Boost if ≥3 categories seen across conversation
        if len(history_categories) >= 3:
            scam_score += 3
        elif len(history_categories) >= 2:
            scam_score += 2
        
        # Repetition bonus — same patterns repeated = more suspicious
        financial_mentions = sum(1 for kw in FINANCIAL_KEYWORDS if kw in history_lower)
        if financial_mentions >= 3:
            scam_score += 2
    
    # Scam threshold
    is_scam = scam_score >= 3
    
    return is_scam, list(set(detected_keywords)), scam_score, categories_hit


def get_scam_type(keywords: List[str]) -> str:
    """Determine the type of scam based on detected keywords."""
    if any(kw in keywords for kw in ["kyc", "verify", "verification", "update"]):
        return "KYC_FRAUD"
    elif any(kw in keywords for kw in ["won", "winner", "prize", "lottery", "reward"]):
        return "LOTTERY_SCAM"
    elif any(kw in keywords for kw in ["blocked", "suspended", "deactivated"]):
        return "ACCOUNT_THREAT"
    elif any(kw in keywords for kw in ["otp", "pin", "cvv"]):
        return "OTP_FRAUD"
    elif any(kw in keywords for kw in ["contains_url"]):
        return "PHISHING"
    else:
        return "GENERAL_FRAUD"


def calculate_confidence(scam_score: int, keyword_count: int, categories_hit: Dict[str, List[str]], history_len: int) -> float:
    """
    Calculate explainable confidence score between 0.0 and 1.0.
    Uses sigmoid normalization weighted by multiple factors.
    """
    if scam_score == 0:
        return 0.05  # Near-zero baseline
    
    # Factor 1: Keyword density (0-1)
    keyword_factor = min(keyword_count / 10.0, 1.0)
    
    # Factor 2: Tactic diversity (0-1)
    tactic_count = len(categories_hit)
    diversity_factor = min(tactic_count / 5.0, 1.0)
    
    # Factor 3: Conversation depth (0-1)
    depth_factor = min(history_len / 8.0, 1.0)
    
    # Factor 4: Raw score sigmoid (0-1)
    # Sigmoid: 1 / (1 + e^(-k*(x - x0)))  where x0=5 (midpoint), k=0.5 (steepness)
    score_sigmoid = 1.0 / (1.0 + math.exp(-0.5 * (scam_score - 5)))
    
    # Weighted combination
    confidence = (
        0.40 * score_sigmoid +
        0.25 * keyword_factor +
        0.20 * diversity_factor +
        0.15 * depth_factor
    )
    
    # Clamp to [0.05, 0.99]
    return round(max(0.05, min(0.99, confidence)), 3)
