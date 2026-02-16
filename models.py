from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class Message(BaseModel):
    sender: str
    text: str
    timestamp: int

class Metadata(BaseModel):
    channel: Optional[str] = "SMS"
    language: Optional[str] = "English"
    locale: Optional[str] = "IN"

class AnalyzeRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: Optional[List[Message]] = []
    metadata: Optional[Metadata] = None

class ExtractedIntelligence(BaseModel):
    bankAccounts: List[str] = []
    upiIds: List[str] = []
    phishingLinks: List[str] = []
    phoneNumbers: List[str] = []
    suspiciousKeywords: List[str] = []
    paymentApps: List[str] = []
    domainRiskScores: Dict[str, str] = {}

class AnalyzeResponse(BaseModel):
    status: str = "success"
    reply: str
    scamDetected: Optional[bool] = None
    extractedIntelligence: Optional[ExtractedIntelligence] = None
    # Anti-Gravity / Competition Fields
    scamAnalysis: Optional[Dict[str, Any]] = None
    scammerProfile: Optional[Dict[str, Any]] = None
    engagementMetrics: Optional[Dict[str, Any]] = None
    systemStatus: Optional[Dict[str, Any]] = None

class GuviCallbackPayload(BaseModel):
    sessionId: str
    scamDetected: bool
    totalMessagesExchanged: int
    extractedIntelligence: dict
    agentNotes: str
    # Optional competition fields for callback too if allowed
    impactMetrics: Optional[Dict[str, Any]] = None
