"""
Session Store - Cross-channel session persistence with SQLite + in-memory cache.
Tracks sessions across platforms and correlates scammer activity.
"""

import asyncio
import aiosqlite
import json
import time
import threading
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrchestraSession:
    """Session data for multi-channel tracking."""
    session_id: str          # Format: "telegram_123456789" or "discord_987654321"
    channel: str             # "telegram", "discord", etc.
    platform_id: str         # Platform-specific user ID
    agent_id: Optional[str] = None
    intelligence: dict = None
    emotional_state: dict = None
    scammer_dna: dict = None
    linked_sessions: List[str] = None  # Cross-platform correlation
    threat_level: str = "low"   # low/medium/high/critical
    created_at: float = None
    last_activity: float = None
    message_count: int = 0
    
    def __post_init__(self):
        if self.intelligence is None:
            self.intelligence = {}
        if self.emotional_state is None:
            self.emotional_state = {"panic": 0.3, "trust": 0.7, "confusion": 0.5}
        if self.scammer_dna is None:
            self.scammer_dna = {}
        if self.linked_sessions is None:
            self.linked_sessions = []
        if self.created_at is None:
            self.created_at = time.time()
        if self.last_activity is None:
            self.last_activity = time.time()
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'OrchestraSession':
        return cls(**data)


class SessionStore:
    """
    Thread-safe session storage with LRU in-memory cache + SQLite persistence.
    Supports cross-channel correlation and entity linking.
    """
    
    def __init__(self, db_path: str = "~/.sentinal/sessions.db", max_memory: int = 100):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.max_memory = max_memory
        self._memory_cache: Dict[str, OrchestraSession] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._db_conn: Optional[aiosqlite.Connection] = None
        
    async def initialize(self):
        """Initialize SQLite database."""
        self._db_conn = await aiosqlite.connect(str(self.db_path))
        await self._db_conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                channel TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                agent_id TEXT,
                intelligence TEXT,
                emotional_state TEXT,
                scammer_dna TEXT,
                linked_sessions TEXT,
                threat_level TEXT,
                created_at REAL,
                last_activity REAL,
                message_count INTEGER
            )
        """)
        await self._db_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_platform_id ON sessions(platform_id)
        """)
        await self._db_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_last_activity ON sessions(last_activity)
        """)
        await self._db_conn.commit()
        logger.info(f"Session store initialized: {self.db_path}")
    
    async def close(self):
        """Close database connection."""
        if self._db_conn:
            await self._db_conn.close()
    
    def _evict_lru(self):
        """Evict least recently used session from memory."""
        if len(self._memory_cache) < self.max_memory:
            return
        
        # Find LRU
        lru_session = min(self._access_times.items(), key=lambda x: x[1])[0]
        del self._memory_cache[lru_session]
        del self._access_times[lru_session]
        logger.debug(f"Evicted LRU session from memory: {lru_session}")
    
    async def get_session(self, session_id: str) -> Optional[OrchestraSession]:
        """Get session from memory or load from DB."""
        with self._lock:
            # Check memory
            if session_id in self._memory_cache:
                self._access_times[session_id] = time.time()
                return self._memory_cache[session_id]
        
        # Load from DB
        async with self._db_conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                session_data = {
                    "session_id": row[0],
                    "channel": row[1],
                    "platform_id": row[2],
                    "agent_id": row[3],
                    "intelligence": json.loads(row[4]) if row[4] else {},
                    "emotional_state": json.loads(row[5]) if row[5] else {},
                    "scammer_dna": json.loads(row[6]) if row[6] else {},
                    "linked_sessions": json.loads(row[7]) if row[7] else [],
                    "threat_level": row[8],
                    "created_at": row[9],
                    "last_activity": row[10],
                    "message_count": row[11]
                }
                session = OrchestraSession.from_dict(session_data)
                
                # Add to memory cache
                with self._lock:
                    self._evict_lru()
                    self._memory_cache[session_id] = session
                    self._access_times[session_id] = time.time()
                
                return session
        
        return None
    
    async def save_session(self, session: OrchestraSession):
        """Save session to both memory and DB."""
        session.last_activity = time.time()
        
        # Update memory
        with self._lock:
            self._evict_lru()
            self._memory_cache[session.session_id] = session
            self._access_times[session.session_id] = time.time()
        
        # Persist to DB
        await self._db_conn.execute("""
            INSERT OR REPLACE INTO sessions 
            (session_id, channel, platform_id, agent_id, intelligence, emotional_state, 
             scammer_dna, linked_sessions, threat_level, created_at, last_activity, message_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.session_id,
            session.channel,
            session.platform_id,
            session.agent_id,
            json.dumps(session.intelligence),
            json.dumps(session.emotional_state),
            json.dumps(session.scammer_dna),
            json.dumps(session.linked_sessions),
            session.threat_level,
            session.created_at,
            session.last_activity,
            session.message_count
        ))
        await self._db_conn.commit()
    
    async def find_by_platform_id(self, platform_id: str) -> List[OrchestraSession]:
        """Find all sessions for a given platform ID (cross-channel search)."""
        sessions = []
        async with self._db_conn.execute(
            "SELECT session_id FROM sessions WHERE platform_id = ?", (platform_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                session = await self.get_session(row[0])
                if session:
                    sessions.append(session)
        return sessions
    
    async def link_sessions(self, session_id1: str, session_id2: str):
        """Link two sessions (bi-directional)."""
        session1 = await self.get_session(session_id1)
        session2 = await self.get_session(session_id2)
        
        if session1 and session2:
            if session_id2 not in session1.linked_sessions:
                session1.linked_sessions.append(session_id2)
                await self.save_session(session1)
            
            if session_id1 not in session2.linked_sessions:
                session2.linked_sessions.append(session_id1)
                await self.save_session(session2)
            
            logger.info(f"Linked sessions: {session_id1} <-> {session_id2}")
    
    async def get_active_sessions(self, timeout_seconds: int = 1800) -> List[OrchestraSession]:
        """Get all sessions active within the last N seconds."""
        cutoff = time.time() - timeout_seconds
        sessions = []
        
        async with self._db_conn.execute(
            "SELECT session_id FROM sessions WHERE last_activity > ?", (cutoff,)
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                session = await self.get_session(row[0])
                if session:
                    sessions.append(session)
        
        return sessions
    
    async def cleanup_old_sessions(self, max_age_seconds: int = 3600):
        """Remove sessions older than max_age from DB."""
        cutoff = time.time() - max_age_seconds
        await self._db_conn.execute(
            "DELETE FROM sessions WHERE last_activity < ?", (cutoff,)
        )
        await self._db_conn.commit()
        logger.info(f"Cleaned up sessions older than {max_age_seconds}s")
    
    def get_stats(self) -> dict:
        """Get session store statistics."""
        with self._lock:
            return {
                "in_memory": len(self._memory_cache),
                "max_memory": self.max_memory,
                "db_path": str(self.db_path)
            }
