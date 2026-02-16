"""
Telegram Channel - Engage scammers via Telegram Bot API.
Uses aiogram for production-grade async Telegram bot.
"""

import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)


class TelegramChannel:
    """Telegram bot channel for scammer engagement."""
    
    def __init__(self, gateway, config: dict):
        self.gateway = gateway
        self.config = config
        self.bot_token = config.get("bot_token")
        self.allowed_users = config.get("allowed_users", [])  # Empty = allow all
        
        if not self.bot_token:
            raise ValueError("Telegram bot_token is required in config")
        
        self.bot = Bot(token=self.bot_token)
        self.dp = Dispatcher()
        
        # Register handlers
        self.dp.message.register(self.handle_start, Command(commands=["start"]))
        self.dp.message.register(self.handle_message)
    
    async def start(self):
        """Start the Telegram bot."""
        logger.info("Starting Telegram channel...")
        try:
            await self.dp.start_polling(self.bot, skip_updates=True)
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")
    
    async def stop(self):
        """Stop the bot."""
        await self.bot.session.close()
    
    async def handle_start(self, message: Message):
        """Handle /start command."""
        user_id = str(message.from_user.id)
        
        # Check allow list
        if self.allowed_users and user_id not in self.allowed_users:
            await message.answer("Sorry, this bot is not available for you.")
            return
        
        await message.answer(
            "Namaste ji, I am Ramesh Kumar. How can I help you?"
        )
    
    async def handle_message(self, message: Message):
        """Handle incoming messages."""
        user_id = str(message.from_user.id)
        message_text = message.text or ""
        
        # Check allow list
        if self.allowed_users and user_id not in self.allowed_users:
            return
        
        # Skip commands
        if message_text.startswith("/"):
            return
        
        logger.info(f"Telegram message from {user_id}: {message_text[:50]}...")
        
        try:
            # Route to gateway
            response = await self.gateway.handle_message(
                channel="telegram",
                platform_id=user_id,
                message_text=message_text,
                conversation_history=[]  # TODO: implement history retrieval
            )
            
            # Send response
            await self.send_message(user_id, response)
            
        except Exception as e:
            logger.error(f"Error handling Telegram message: {e}")
            await message.answer("Sorry ji, I didn't understand. Please repeat.")
    
    async def send_message(self, platform_id: str, text: str):
        """Send message via Telegram API."""
        try:
            await self.bot.send_message(chat_id=platform_id, text=text)
            logger.info(f"Sent Telegram message to {platform_id}: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
