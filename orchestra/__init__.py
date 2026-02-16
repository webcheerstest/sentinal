"""
Sentinal Orchestra - Multi-channel honeypot orchestration layer.

Inspired by PicoClaw's ultra-lightweight architecture, adapted for Python.
"""

__version__ = "1.0.0"
__author__ = "Sentinal Team"

from .gateway import OrchestraGateway
from .agent_pool import AgentPool
from .session_store import SessionStore

__all__ = ["OrchestraGateway", "AgentPool", "SessionStore"]
