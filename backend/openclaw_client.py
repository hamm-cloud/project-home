"""
OpenClaw Session Client
Direct integration with OpenClaw's session API for Hamm voice interface
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)


class OpenClawClient:
    """Client for interacting with OpenClaw sessions"""
    
    def __init__(self, base_url: str = "http://localhost:14444"):
        self.base_url = base_url
        self.session_id = None
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def create_session(self, session_name: str = "hamm_voice") -> Optional[str]:
        """Create a new OpenClaw session for Hamm"""
        try:
            # Create a dedicated Hamm session with memory access
            payload = {
                "id": session_name,
                "model": "anthropic/claude-haiku-4-5",  # Fast model for voice
                "runtime": "acp",
                "config": {
                    "workspace": "/home/openclaw/.openclaw/workspace",
                    "memory_access": True,
                    "load_context": ["SOUL.md", "USER.md", "MEMORY.md", "AGENTS.md"]
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/sessions",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get("id", session_name)
                logger.info(f"Created OpenClaw session: {self.session_id}")
                return self.session_id
            else:
                logger.error(f"Failed to create session: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    async def send_message(self, message: str, session_id: Optional[str] = None) -> Optional[str]:
        """Send a message to the OpenClaw session and get response"""
        try:
            sid = session_id or self.session_id
            if not sid:
                # Try to create a session if none exists
                sid = await self.create_session()
                if not sid:
                    return "I'm having trouble connecting to my main system."
            
            # Send the message
            response = await self.client.post(
                f"{self.base_url}/api/sessions/{sid}/message",
                json={
                    "message": message,
                    "metadata": {
                        "source": "voice",
                        "timestamp": datetime.now().isoformat()
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                logger.error(f"Message failed: {response.status_code}")
                # Fallback response
                return "I heard you, but I'm having trouble processing right now."
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return "Sorry, I'm having connection issues."
    
    async def close(self):
        """Close the client connection"""
        await self.client.aclose()


# Global client instance
openclaw_client = None


async def get_openclaw_client() -> OpenClawClient:
    """Get or create the OpenClaw client singleton"""
    global openclaw_client
    if openclaw_client is None:
        openclaw_client = OpenClawClient()
        await openclaw_client.create_session("hamm_voice")
    return openclaw_client


async def send_to_hamm(message: str) -> str:
    """Simple interface to send a message to Hamm"""
    client = await get_openclaw_client()
    response = await client.send_message(message)
    return response or "I'm here, but having trouble with my connection."