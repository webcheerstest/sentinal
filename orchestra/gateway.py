"""
Orchestra Gateway - Multi-channel event router and orchestrator.
Coordinates messages across Telegram, Discord, and other platforms.
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestra.session_store import SessionStore, OrchestraSession
from orchestra.agent_pool import AgentPool
from orchestra.providers.openrouter import OpenRouterProvider

# Import existing Sentinal modules
from scam_detector import detect_scam, get_scam_type, calculate_confidence
from intelligence import extract_all_intelligence
from agent_persona import generate_honeypot_response
from scammer_dna import ScammerDNA
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, FREE_MODELS

logger = logging.getLogger(__name__)


class OrchestraGateway:
    """
    Multi-channel orchestration gateway.
    Routes messages from different platforms to appropriate agents.
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.session_store: Optional[SessionStore] = None
        self.agent_pool: Optional[AgentPool] = None
        self.llm_provider: Optional[OpenRouterProvider] = None
        self.dna_engine = ScammerDNA()
        
        # Channel instances
        self.channels: Dict[str, any] = {}
        
        # Message queue for async processing
        self.message_queue = asyncio.Queue(maxsize=100)
        self._running = False
    
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Orchestra Gateway...")
        
        # Initialize session store
        db_path = self.config.get("session_store", {}).get("sqlite_path", "~/.sentinal/sessions.db")
        max_memory = self.config.get("session_store", {}).get("max_in_memory", 100)
        self.session_store = SessionStore(db_path=db_path, max_memory=max_memory)
        await self.session_store.initialize()
        
        # Initialize agent pool
        max_agents = self.config.get("gateway", {}).get("max_concurrent_agents", 10)
        self.agent_pool = AgentPool(max_agents=max_agents)
        
        # Initialize LLM provider
        self.llm_provider = OpenRouterProvider(
            api_key=OPENROUTER_API_KEY,
            api_base=OPENROUTER_BASE_URL,
            free_models=FREE_MODELS
        )
        
        logger.info("Orchestra Gateway initialized successfully")
    
    async def handle_message(
        self,
        channel: str,
        platform_id: str,
        message_text: str,
        conversation_history: list = None
    ) -> str:
        """
        Handle incoming message from any channel.
        
        Args:
            channel: Channel name (e.g., "telegram", "discord")
            platform_id: Platform-specific user ID
            message_text: The message text
            conversation_history: Optional conversation history
        
        Returns:
            Response text to send back
        """
        session_id = f"{channel}_{platform_id}"
        conversation_history = conversation_history or []
        
        try:
            # Get or create session
            session = await self.session_store.get_session(session_id)
            if not session:
                session = OrchestraSession(
                    session_id=session_id,
                    channel=channel,
                    platform_id=platform_id
                )
            
            # Get or spawn agent
            agent = await self.agent_pool.get_or_spawn_agent(session_id, channel)
            session.agent_id = agent.agent_id
            agent.message_count += 1
            session.message_count += 1
            
            # === SCAM DETECTION ===
            scam_detected, keywords, scam_score, categories_hit = detect_scam(
                message_text, conversation_history
            )
            scam_type = get_scam_type(keywords) if scam_detected else None
            
            # Calculate confidence
            confidence = calculate_confidence(
                scam_score=scam_score,
                keyword_count=len(keywords),
                categories_hit=categories_hit,
                history_len=len(conversation_history)
            )
            
            # === INTELLIGENCE EXTRACTION ===
            intel = extract_all_intelligence(message_text)
            
            # Merge intelligence
            if not session.intelligence:
                session.intelligence = {}
            
            for key in ["bankAccounts", "upiIds", "phishingLinks", "phoneNumbers", "paymentApps"]:
                if key not in session.intelligence:
                    session.intelligence[key] = []
                session.intelligence[key] = list(set(
                    session.intelligence[key] + getattr(intel, key, [])
                ))
            
            if not session.intelligence.get("domainRiskScores"):
                session.intelligence["domainRiskScores"] = {}
            session.intelligence["domainRiskScores"].update(intel.domainRiskScores)
            
            # === EMOTIONAL STATE UPDATE ===
            if not session.emotional_state:
                session.emotional_state = {"panic": 0.3, "trust": 0.7, "confusion": 0.5}
            
            # Simple emotional update (reuse existing logic concept)
            text_lower = message_text.lower()
            if any(w in text_lower for w in ["blocked", "police", "arrest"]):
                session.emotional_state["panic"] = min(1.0, session.emotional_state.get("panic", 0.3) + 0.15)
            if any(w in text_lower for w in ["official", "government", "verify"]):
                session.emotional_state["trust"] = min(1.0, session.emotional_state.get("trust", 0.7) + 0.08)
            
            # === SCAMMER DNA ===
            full_history = conversation_history.copy()
            full_history.append({
                "sender": "scammer",
                "text": message_text,
                "timestamp": int(asyncio.get_event_loop().time() * 1000)
            })
            
            signature, features = self.dna_engine.generate_fingerprint_from_history(
                full_history, session_id
            )
            session.scammer_dna = {
                "signature": signature,
                "features": features
            }
            
            # === THREAT SCORING (simple version) ===
            intel_count = len(session.intelligence.get("bankAccounts", [])) + \
                         len(session.intelligence.get("upiIds", [])) + \
                         len(session.intelligence.get("phoneNumbers", []))
            
            if intel_count >= 3 or confidence > 0.9:
                session.threat_level = "critical"
            elif intel_count >= 2 or confidence > 0.75:
                session.threat_level = "high"
            elif confidence > 0.5:
                session.threat_level = "medium"
            else:
                session.threat_level = "low"
            
            # === GENERATE RESPONSE ===
            if scam_detected or session.message_count > 1:
                response = await generate_honeypot_response(
                    current_message=message_text,
                    conversation_history=conversation_history,
                    scam_detected=True,
                    scam_type=scam_type,
                    emotional_state=session.emotional_state
                )
            else:
                response = "Hello ji, who is this? I think you have wrong number."
            
            # === SAVE SESSION ===
            await self.session_store.save_session(session)
            
            logger.info(f"[{channel}] {session_id}: threat={session.threat_level}, intel={intel_count}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling message from {channel}/{platform_id}: {e}")
            import traceback
            traceback.print_exc()
            return "Sorry, I didn't understand. Can you explain again?"
    
    async def start(self):
        """Start the gateway and all channels."""
        self._running = True
        logger.info("Orchestra Gateway started")
        
        # Start channels based on config
        channels_config = self.config.get("channels", {})
        
        if channels_config.get("telegram", {}).get("enabled"):
            from orchestra.channels.telegram import TelegramChannel
            telegram_channel = TelegramChannel(
                gateway=self,
                config=channels_config["telegram"]
            )
            self.channels["telegram"] = telegram_channel
            asyncio.create_task(telegram_channel.start())
            logger.info("Telegram channel started")
        
        # Keep gateway running
        while self._running:
            await asyncio.sleep(1)
    
    async def stop(self):
        """Stop the gateway and cleanup."""
        self._running = False
        logger.info("Stopping Orchestra Gateway...")
        
        # Stop all channels
        for channel in self.channels.values():
            if hasattr(channel, 'stop'):
                await channel.stop()
        
        # Cleanup
        if self.session_store:
            await self.session_store.close()
        
        logger.info("Orchestra Gateway stopped")
    
    def get_stats(self) -> dict:
        """Get gateway statistics."""
        return {
            "agent_pool": self.agent_pool.get_stats() if self.agent_pool else {},
            "session_store": self.session_store.get_stats() if self.session_store else {},
            "active_channels": list(self.channels.keys())
        }
