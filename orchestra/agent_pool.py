"""
Agent Pool Manager - Dynamic honeypot persona spawning with resource limits.
Manages up to 10 concurrent agents with LRU eviction.
"""

import asyncio
import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Agent:
    """Honeypot agent instance."""
    agent_id: str
    session_id: str
    channel: str
    created_at: float
    last_activity: float
    message_count: int = 0
    
    def touch(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()


class AgentPool:
    """
    Pool-based agent instance manager.
    Spawns new agents on demand, evicts LRU when pool is full.
    """
    
    def __init__(self, max_agents: int = 10):
        self.max_agents = max_agents
        self._agents: Dict[str, Agent] = {}
        self._session_to_agent: Dict[str, str] = {}  # session_id -> agent_id
        self._lock = asyncio.Lock()
    
    async def get_or_spawn_agent(self, session_id: str, channel: str) -> Agent:
        """Get existing agent for session or spawn a new one."""
        async with self._lock:
            # Check if agent exists for this session
            if session_id in self._session_to_agent:
                agent_id = self._session_to_agent[session_id]
                if agent_id in self._agents:
                    agent = self._agents[agent_id]
                    agent.touch()
                    return agent
            
            # Need to spawn new agent
            if len(self._agents) >= self.max_agents:
                self._evict_lru()
            
            agent_id = f"agent_{int(time.time() * 1000)}_{len(self._agents)}"
            agent = Agent(
                agent_id=agent_id,
                session_id=session_id,
                channel=channel,
                created_at=time.time(),
                last_activity=time.time()
            )
            
            self._agents[agent_id] = agent
            self._session_to_agent[session_id] = agent_id
            
            logger.info(f"Spawned new agent: {agent_id} for session {session_id}")
            return agent
    
    def _evict_lru(self):
        """Evict least recently used agent."""
        if not self._agents:
            return
        
        lru_agent_id = min(self._agents.items(), key=lambda x: x[1].last_activity)[0]
        lru_agent = self._agents[lru_agent_id]
        
        # Remove from both dicts
        del self._agents[lru_agent_id]
        if lru_agent.session_id in self._session_to_agent:
            del self._session_to_agent[lru_agent.session_id]
        
        logger.info(f"Evicted LRU agent: {lru_agent_id} (session: {lru_agent.session_id})")
    
    async def get_agent(self, session_id: str) -> Optional[Agent]:
        """Get agent for a session (doesn't spawn if not exists)."""
        async with self._lock:
            if session_id in self._session_to_agent:
                agent_id = self._session_to_agent[session_id]
                return self._agents.get(agent_id)
            return None
    
    async def remove_agent(self, agent_id: str):
        """Gracefully remove an agent."""
        async with self._lock:
            if agent_id in self._agents:
                agent = self._agents[agent_id]
                del self._agents[agent_id]
                if agent.session_id in self._session_to_agent:
                    del self._session_to_agent[agent.session_id]
                logger.info(f"Removed agent: {agent_id}")
    
    def get_stats(self) -> dict:
        """Get pool statistics."""
        return {
            "active_agents": len(self._agents),
            "max_agents": self.max_agents,
            "utilization": len(self._agents) / self.max_agents
        }
    
    def list_agents(self) -> list:
        """List all active agents."""
        return [
            {
                "agent_id": agent.agent_id,
                "session_id": agent.session_id,
                "channel": agent.channel,
                "message_count": agent.message_count,
                "age_seconds": time.time() - agent.created_at
            }
            for agent in self._agents.values()
        ]
