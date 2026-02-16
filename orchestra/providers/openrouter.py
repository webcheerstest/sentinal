"""OpenRouter LLM provider - reuses existing Sentinal config."""

import httpx
import logging
from typing import List, Dict, Optional
from .base import LLMProvider

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider using existing Sentinal configuration."""
    
    def __init__(self, api_key: str, api_base: str, free_models: List[str]):
        self.api_key = api_key
        self.api_base = api_base
        self.free_models = free_models
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        max_tokens: int = 150,
        temperature: float = 0.8
    ) -> Optional[str]:
        """Generate response using OpenRouter API."""
        models_to_try = [model] if model else self.free_models
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for model_name in models_to_try:
                try:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://sentinal-honeypot.app",
                            "X-Title": "Sentinal Orchestra"
                        },
                        json={
                            "model": model_name,
                            "messages": messages,
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                        },
                        timeout=8.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        if reply:
                            return reply
                    
                except httpx.TimeoutException:
                    logger.warning(f"Model {model_name} timed out")
                except Exception as e:
                    logger.warning(f"Model {model_name} failed: {e}")
        
        return None
    
    def get_available_models(self) -> List[str]:
        """Get list of free models."""
        return self.free_models
