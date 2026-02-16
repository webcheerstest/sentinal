# Sentinal Orchestra Architecture

## Overview

**Sentinal Orchestra** is a PicoClaw-inspired orchestration layer that transforms Sentinal from a single-endpoint honeypot into a distributed, multi-channel AI scam detection system. It coordinates multiple honeypot personas across different platforms (Telegram, Discord, WhatsApp) while maintaining shared intelligence and cross-session correlation.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SENTINAL ORCHESTRA                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │   Telegram   │    │   Discord    │    │   WhatsApp   │     │
│  │   Channel    │    │   Channel    │    │   Channel    │     │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘     │
│         │                   │                   │              │
│         └───────────────────┼───────────────────┘              │
│                             ↓                                  │
│                    ┌────────────────┐                          │
│                    │    Gateway     │                          │
│                    │  Event Router  │                          │
│                    └────────┬───────┘                          │
│                             ↓                                  │
│         ┌───────────────────┼───────────────────┐              │
│         ↓                   ↓                   ↓              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │ Agent Pool  │    │   Skills    │    │   Session   │       │
│  │  Manager    │    │   System    │    │    Store    │       │
│  └─────┬───────┘    └─────┬───────┘    └─────┬───────┘       │
│        │                   │                   │              │
│        └───────────────────┼───────────────────┘              │
│                            ↓                                  │
│              ┌──────────────────────────┐                     │
│              │   Existing Sentinal      │                     │
│              │   (scam_detector,        │                     │
│              │    intelligence,         │                     │
│              │    agent_persona)        │                     │
│              └──────────────────────────┘                     │
│                            ↓                                  │
│              ┌──────────────────────────┐                     │
│              │   Heartbeat Aggregator   │                     │
│              │   (30min intelligence    │                     │
│              │    reporting to GUVI)    │                     │
│              └──────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Gateway (`orchestra/gateway.py`)

**Purpose**: Multi-channel event router that receives messages from different platforms and coordinates responses.

**Responsibilities**:
- Route incoming messages to appropriate agent
- Maintain channel-to-session mappings
- Handle async message queuing
- Provide unified interface for all channels

**Key Features**:
- Async event loop with `asyncio.Queue`
- Channel abstraction (platform-agnostic)
- Message deduplication
- Rate limiting per channel

---

### 2. Agent Pool Manager (`orchestra/agent_pool.py`)

**Purpose**: Dynamic honeypot persona spawning and lifecycle management.

**Responsibilities**:
- Create new honeypot instances on demand
- Pool-based resource management (max 10 concurrent)
- Agent-to-session binding
- Graceful agent shutdown

**Agent Lifecycle**:
```
Scammer connects → Gateway routes → Agent Pool checks existing agents
                                              ↓
                              New scammer? Spawn new agent (if pool < 10)
                              Existing scammer? Route to existing agent
                                              ↓
                              Agent generates response using persona/emotional state
                                              ↓
                              Response sent via channel → Intelligence extracted
```

**Memory Management**:
- LRU eviction when pool reaches max capacity
- Shared LLM cache across all agents
- Lazy persona initialization

---

### 3. Session Store (`orchestra/session_store.py`)

**Purpose**: Cross-channel session persistence and correlation.

**Storage Strategy**:
- **In-Memory**: Active sessions (last 30min) — fast access
- **SQLite**: Inactive sessions — persistent storage
- **LRU Cache**: Max 100 in-memory sessions

**Schema**:
```python
{
    "session_id": "telegram_123456789",
    "channel": "telegram",
    "platform_id": "123456789",
    "agent_id": "agent_001",
    "intelligence": {...},
    "emotional_state": {...},
    "scammer_dna": {...},
    "linked_sessions": ["discord_987654321"],  # Cross-platform correlation
    "threat_level": "high",
    "created_at": 1707810000,
    "last_activity": 1707811800
}
```

---

### 4. Skills System (`orchestra/skills/`)

**Purpose**: Pluggable intelligence analysis modules that run in parallel.

**Skill Interface**:
```python
class ScamSkill:
    def analyze(self, message: str, session: Session) -> SkillResult:
        """Analyze message and return results"""
        pass
    
    def get_confidence(self) -> float:
        """Return confidence score 0.0-1.0"""
        pass
```

**Built-in Skills**:

| Skill | Purpose | Output |
|-------|---------|--------|
| `ScamClassifier` | Multi-label categorization | KYC/Lottery/Investment/Tech Support |
| `EntityLinker` | Cross-session correlation | Linked phone numbers, UPIs, accounts |
| `ThreatScorer` | Real-time risk assessment | Low/Medium/High/Critical |

**Skill Execution**:
- All skills run concurrently using `asyncio.gather()`
- Results aggregated by confidence-weighted voting
- Failed skills don't block the pipeline

---

### 5. Channels (`orchestra/channels/`)

**Purpose**: Platform-specific message adapters.

**Channel Interface**:
```python
class Channel:
    async def start(self):
        """Start listening for messages"""
        pass
    
    async def send_message(self, platform_id: str, text: str):
        """Send message to platform"""
        pass
    
    async def handle_message(self, platform_id: str, message: str):
        """Process incoming message"""
        pass
```

**Supported Channels**:

| Platform | Library | Status |
|----------|---------|--------|
| Telegram | `aiogram` | ✅ Phase 2 |
| Discord | `discord.py` | 🔜 Phase 3 |
| WhatsApp | `whatsapp-cloud-api` | 🔜 Phase 4 |

---

### 6. Heartbeat (`orchestra/heartbeat.py`)

**Purpose**: Automated intelligence aggregation and reporting.

**Schedule**: Every 30 minutes

**Tasks**:
1. Aggregate intelligence across all active sessions
2. Generate cross-session correlation report
3. Calculate global threat metrics
4. Send aggregated intelligence to GUVI
5. Cleanup inactive sessions (>5min idle)

**Metrics Reported**:
- Total scammers engaged (by channel)
- Top threat actors (by intelligence density)
- New UPI IDs / bank accounts discovered
- Cross-platform scammer matches

---

## Data Flow

### Incoming Message Flow

```
1. Telegram bot receives message from scammer (user_id: 123456789)
        ↓
2. Channel adapter calls gateway.handle_message("telegram", "123456789", "Your account blocked!")
        ↓
3. Gateway checks session_store for existing session
        ↓
4. If new: agent_pool.spawn_agent(session_id="telegram_123456789")
   If existing: agent_pool.get_agent(session_id)
        ↓
5. Skills run in parallel:
   - ScamClassifier → "KYC_FRAUD"
   - ThreatScorer → "high"
   - EntityLinker → Check if phone/UPI seen in other sessions
        ↓
6. Agent generates response using:
   - Existing scam_detector.py (combo scoring)
   - Existing agent_persona.py (async LLM)
   - Emotional state from session
        ↓
7. Response sent via channel.send_message()
        ↓
8. Intelligence stored in session_store (both in-memory + SQLite)
        ↓
9. If new intelligence found → Smart callback to GUVI
```

---

## Integration with Existing Sentinal

### Minimal Changes to Core

The orchestra layer is **additive**, not destructive:

| Existing Module | Used By Orchestra | Changes Needed |
|----------------|-------------------|----------------|
| `scam_detector.py` | ✅ Direct import | None |
| `intelligence.py` | ✅ Direct import | None |
| `agent_persona.py` | ✅ Direct import | None |
| `session_manager.py` | ⚠️ Wrapped by `session_store.py` | Extend for cross-channel |
| `scammer_dna.py` | ✅ Direct import | None |
| `cache.py` | ✅ Shared across agents | None |
| `rate_limiter.py` | ✅ Extended for channels | Add channel-level limits |
| `main.py` | ⚠️ Add `/orchestra/*` routes | Add new endpoints |

### New API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /orchestra/stats` | Live metrics (active agents, sessions by channel) |
| `GET /orchestra/agents` | List active agents and their sessions |
| `POST /orchestra/shutdown/{agent_id}` | Gracefully stop an agent |
| `GET /orchestra/session/{session_id}` | Cross-channel session details |

---

## Configuration

### `config/orchestra.json`

```json
{
  "gateway": {
    "max_concurrent_agents": 10,
    "message_queue_size": 100
  },
  "session_store": {
    "max_in_memory": 100,
    "sqlite_path": "~/.sentinal/sessions.db",
    "inactive_timeout_minutes": 30
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "bot_token": "YOUR_BOT_TOKEN",
      "allowed_users": []  # Empty = engage with everyone
    },
    "discord": {
      "enabled": false,
      "bot_token": "",
      "allowed_guilds": []
    }
  },
  "skills": {
    "enabled": ["scam_classifier", "entity_linker", "threat_scorer"],
    "parallel_execution": true
  },
  "heartbeat": {
    "enabled": true,
    "interval_minutes": 30
  }
}
```

---

## Memory Optimization

### Target: <100MB Total System Memory

| Component | Memory Budget | Strategy |
|-----------|---------------|----------|
| Agent Pool (10 agents) | ~30MB | Shared LLM cache, lazy loading |
| Session Store (100 active) | ~20MB | LRU eviction, SQLite offload |
| Channel Bots | ~15MB | Single bot instance per platform |
| Skills System | ~10MB | Lightweight numpy-free classifiers |
| Core Sentinal | ~25MB | Existing optimizations |

**Total**: ~100MB (vs PicoClaw's <10MB in Go, but 10x better than typical Python bots)

---

## Competition Advantages

### Why Orchestra Wins

1. **Multi-Platform Presence** — Engage scammers where they operate (Telegram #1, Discord #2)
2. **Coordinated Intelligence** — Link same scammer across platforms using phone/UPI
3. **Automated Reporting** — Heartbeat ensures continuous intelligence feed to GUVI
4. **Threat Prioritization** — Focus on high-value targets (multiple platforms, high intel)
5. **Scalable Architecture** — Add new channels/skills without code changes

### Example Multi-Channel Scenario

```
Scammer engages on Telegram:
  → Agent 1 extracts phone: +919876543210
  → Stores in session_store

Same scammer tries Discord (different username):
  → Agent 2 extracts same phone: +919876543210
  → EntityLinker skill matches across sessions
  → Session linked: "This is the same scammer from Telegram!"
  → Combined intelligence sent to GUVI
  → Threat level escalated to "critical"
```

---

## Deployment

### Development
```bash
cd /Users/MyWork/My\ Apps/Sentinal
python3 -m pip install -r requirements_orchestra.txt
python3 orchestra/gateway.py
```

### Production (VPS)
```bash
# Main API (existing)
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Orchestra Gateway (new)
python3 orchestra/gateway.py &
```

---

## Technology Stack

| Layer | Technology | Justification |
|-------|------------|---------------|
| Async Runtime | `asyncio` | Native Python concurrency |
| Telegram | `aiogram 3.x` | Production-grade, async-native |
| Discord | `discord.py` | Most popular Python Discord lib |
| Session DB | `aiosqlite` | Async SQLite, no Redis dependency |
| HTTP Client | `httpx` | Already used in existing Sentinal |
| LLM | Shared OpenRouter | Reuse existing integration |

---

## Roadmap

- ✅ Phase 1: Core orchestration (gateway, agent pool, session store)
- ✅ Phase 2: Telegram integration
- 🔜 Phase 3: Discord integration
- 🔜 Phase 4: WhatsApp integration
- 🔜 Phase 5: Advanced skills (image analysis, voice scam detection)

---

## File Tree

```
/Users/MyWork/My Apps/Sentinal/
├── ORCHESTRA_ARCHITECTURE.md (this file)
├── orchestra/
│   ├── __init__.py
│   ├── gateway.py (600 lines)
│   ├── agent_pool.py (300 lines)
│   ├── session_store.py (400 lines)
│   ├── heartbeat.py (200 lines)
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py (100 lines)
│   │   ├── telegram.py (500 lines)
│   │   └── discord.py (500 lines)
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── scam_classifier.py (300 lines)
│   │   ├── entity_linker.py (200 lines)
│   │   └── threat_scorer.py (150 lines)
│   └── providers/
│       ├── __init__.py
│       ├── base.py (100 lines)
│       └── openrouter.py (150 lines)
├── config/
│   └── orchestra.json
└── requirements_orchestra.txt
```

**Total New Code**: ~3,500 lines
**Memory Footprint**: <100MB (target)
**Boot Time**: <3s for full gateway
