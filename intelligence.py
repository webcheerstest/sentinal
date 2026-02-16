import re
import math
import logging
from typing import List, Dict
from models import ExtractedIntelligence

logger = logging.getLogger(__name__)

# Pre-compiled patterns for performance
URL_PATTERN = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
PHONE_PATTERN = re.compile(r'\b(?:\+91|91)?[6-9]\d{9}\b')
UPI_PATTERN = re.compile(r'[a-zA-Z0-9.\-_]+@[a-zA-Z]{3,}')
BANK_ACCOUNT_PATTERN = re.compile(r'\b\d{9,18}\b')
IP_URL_PATTERN = re.compile(r'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')

# Payment app patterns (case-insensitive)
PAYMENT_APPS = {
    "gpay": ["gpay", "google pay", "googlepay"],
    "phonepe": ["phonepe", "phone pe"],
    "paytm": ["paytm", "pay tm"],
    "sbi_yono": ["sbi yono", "yono", "yono sbi"],
    "bhim": ["bhim", "bhim upi"],
    "amazon_pay": ["amazon pay", "amazonpay"],
    "mobikwik": ["mobikwik"],
    "freecharge": ["freecharge"],
    "cred": ["cred pay", "cred"],
}

# Suspicious TLDs for domain reputation
HIGH_RISK_TLDS = {".xyz", ".top", ".click", ".info", ".bid", ".win", ".loan", ".racing", ".gq", ".tk", ".ml", ".cf", ".ga"}
MEDIUM_RISK_TLDS = {".online", ".site", ".club", ".buzz", ".icu", ".work", ".fun"}


def calculate_entropy(digits: str) -> float:
    """Calculate Shannon entropy of a digit string to filter random numbers."""
    if not digits:
        return 0.0
    freq = {}
    for d in digits:
        freq[d] = freq.get(d, 0) + 1
    length = len(digits)
    entropy = 0.0
    for count in freq.values():
        p = count / length
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def extract_bank_accounts(text: str) -> List[str]:
    """Extract potential bank account numbers with entropy filtering."""
    matches = BANK_ACCOUNT_PATTERN.findall(text)
    
    filtered = []
    for m in matches:
        # Skip likely phone numbers (10 digits starting with 6-9)
        if len(m) == 10 and m[0] in '6789':
            continue
        # Skip 12-digit numbers that look like 91+phone (e.g., 919876543210)
        if len(m) == 12 and m.startswith('91') and m[2] in '6789':
            continue
        # Skip 11-digit numbers starting with country code pattern
        if len(m) == 11 and m[0] in '6789':
            continue
        
        # Entropy filter: real account numbers have some structure
        # Random sequences like timestamps or IDs tend to have higher entropy
        entropy = calculate_entropy(m)
        if entropy < 2.0:
            # Too low entropy (e.g., all same digits like 1111111111)
            continue
        if len(m) >= 12 and entropy > 3.3:
            # Very high entropy for long numbers — likely random/timestamp
            continue
        
        filtered.append(m)
        
    return list(set(filtered))


def extract_upi_ids(text: str) -> List[str]:
    """Extract UPI IDs."""
    return list(set(UPI_PATTERN.findall(text)))


def extract_phishing_links(text: str) -> List[str]:
    """Extract suspicious URLs."""
    return list(set(URL_PATTERN.findall(text)))


def score_domain_risk(urls: List[str]) -> Dict[str, str]:
    """
    Score domain risk based on TLD and URL structure.
    Returns {url: risk_level} where risk_level is "high", "medium", or "low".
    """
    risk_scores = {}
    
    for url in urls:
        url_lower = url.lower()
        risk = "low"
        
        # Check for IP-based URLs (always high risk)
        if IP_URL_PATTERN.search(url_lower):
            risk = "high"
        else:
            # Check TLD risk
            for tld in HIGH_RISK_TLDS:
                if tld in url_lower:
                    risk = "high"
                    break
            
            if risk == "low":
                for tld in MEDIUM_RISK_TLDS:
                    if tld in url_lower:
                        risk = "medium"
                        break
        
        # Additional signals
        if risk != "high":
            # Very long URLs are suspicious
            if len(url) > 100:
                risk = "medium" if risk == "low" else risk
            # Contains common phishing patterns
            if any(kw in url_lower for kw in ["login", "verify", "secure", "update", "confirm", "bank"]):
                risk = "high" if risk == "medium" else "medium"
        
        risk_scores[url] = risk
    
    return risk_scores


def extract_phone_numbers(text: str) -> List[str]:
    """Extract Indian phone numbers with normalization."""
    matches = PHONE_PATTERN.findall(text)
    normalized = []
    
    for m in matches:
        if m.startswith('91') and len(m) == 12:
            normalized.append('+' + m)
        elif len(m) == 10:
            normalized.append('+91' + m)
        else:
            normalized.append(m)
            
    return list(set(normalized))


def extract_suspicious_keywords(text: str) -> List[str]:
    """Extract suspicious keywords from text."""
    keywords = []
    text_lower = text.lower()
    
    suspicious_terms = [
        "urgent", "immediately", "blocked", "suspended", "verify", 
        "kyc", "otp", "pin", "update", "click", "link", "won", 
        "prize", "lottery", "reward", "free", "account", "bank",
        "transfer", "payment", "money", "upi", "customer care",
        "helpline", "support", "official", "government", "rbi"
    ]
    
    for term in suspicious_terms:
        if term in text_lower:
            keywords.append(term)
    
    return list(set(keywords))


def extract_payment_apps(text: str) -> List[str]:
    """Extract mentions of Indian payment apps."""
    found_apps = []
    text_lower = text.lower()
    
    for app_name, patterns in PAYMENT_APPS.items():
        for pattern in patterns:
            if pattern in text_lower:
                found_apps.append(app_name)
                break  # Found this app, move to next
    
    return list(set(found_apps))


def extract_all_intelligence(text: str, existing: ExtractedIntelligence = None) -> ExtractedIntelligence:
    """Extract all intelligence from text and merge with existing."""
    urls = extract_phishing_links(text)
    domain_risks = score_domain_risk(urls)
    
    new_intel = ExtractedIntelligence(
        bankAccounts=extract_bank_accounts(text),
        upiIds=extract_upi_ids(text),
        phishingLinks=urls,
        phoneNumbers=extract_phone_numbers(text),
        suspiciousKeywords=extract_suspicious_keywords(text),
        paymentApps=extract_payment_apps(text),
        domainRiskScores=domain_risks
    )
    
    if existing:
        # Merge domain risk scores (new overrides old for same URL)
        merged_domain_risks = {**existing.domainRiskScores, **new_intel.domainRiskScores}
        
        return ExtractedIntelligence(
            bankAccounts=list(set(existing.bankAccounts + new_intel.bankAccounts)),
            upiIds=list(set(existing.upiIds + new_intel.upiIds)),
            phishingLinks=list(set(existing.phishingLinks + new_intel.phishingLinks)),
            phoneNumbers=list(set(existing.phoneNumbers + new_intel.phoneNumbers)),
            suspiciousKeywords=list(set(existing.suspiciousKeywords + new_intel.suspiciousKeywords)),
            paymentApps=list(set(existing.paymentApps + new_intel.paymentApps)),
            domainRiskScores=merged_domain_risks
        )
    
    return new_intel


def extract_from_conversation(messages: List[dict]) -> ExtractedIntelligence:
    """Extract intelligence from entire conversation history."""
    intel = ExtractedIntelligence()
    
    for msg in messages:
        text = msg.get("text", "")
        intel = extract_all_intelligence(text, intel)
    
    return intel
