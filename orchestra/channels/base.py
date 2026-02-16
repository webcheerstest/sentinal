"""Base channel interface."""

from abc import ABC, abstractmethod


class Channel(ABC):
    """Abstract base class for all channels (Telegram, Discord, etc.)."""
    
    @abstractmethod
    async def start(self):
        """Start listening for messages."""
        pass
    
    @abstractmethod
    async def send_message(self, platform_id: str, text: str):
        """Send message to platform."""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the channel gracefully."""
        pass
