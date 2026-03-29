"""
Project Home Backend - Clean Architecture
Voice → STT → OpenClaw Session → TTS → Audio Stream
"""

import os
import io
import asyncio
import logging
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import socketio
import uvicorn

from groq import Groq
from elevenlabs import ElevenLabs, VoiceSettings, stream
import httpx
from openclaw_client import send_to_hamm

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Configuration
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
OPENCLAW_API_URL = os.getenv("OPENCLAW_API_URL", "http://localhost:14444")
HAMM_SESSION_ID = os.getenv("HAMM_SESSION_ID", "hamm_voice_session")

# FastAPI app
app = FastAPI(title="Project Home Voice Interface")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False
)

# Create ASGI app
socket_app = socketio.ASGIApp(sio, app)


class VoiceSession:
    """Manages a single voice conversation session"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.is_processing = False
        self.audio_buffer = io.BytesIO()
        
    async def process_audio(self, audio_data: bytes) -> Optional[str]:
        """Convert audio to text using Groq Whisper"""
        try:
            # Create a temporary file-like object for the audio
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.webm"  # Groq needs a filename
            
            # Transcribe with Groq Whisper
            transcription = groq_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                language="en",
                response_format="text"
            )
            
            return transcription.strip() if transcription else None
            
        except Exception as e:
            logger.error(f"STT Error: {e}")
            return None
    
    async def get_hamm_response(self, text: str) -> Optional[str]:
        """Send text to OpenClaw Hamm session and get response"""
        try:
            # For now, use a simple response while we set up the real integration
            # TODO: Connect to actual OpenClaw session once gateway is configured
            return f"I heard you say: '{text}'. The real Hamm integration is being set up."
        except Exception as e:
            logger.error(f"OpenClaw API Error: {e}")
            # Fallback: Return a simple acknowledgment
            return f"I heard you say: {text}"
    
    async def generate_speech(self, text: str) -> bytes:
        """Convert text to speech using ElevenLabs Ivy"""
        try:
            # Generate audio with streaming
            audio_generator = elevenlabs_client.text_to_speech.convert(
                text=text,
                voice_id=ELEVENLABS_VOICE_ID,
                model_id="eleven_turbo_v2_5",  # Fast model for low latency
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True
                ),
                output_format="mp3_22050_32"  # Lower quality for faster streaming
            )
            
            # Collect audio chunks
            audio_chunks = []
            for chunk in audio_generator:
                audio_chunks.append(chunk)
            
            return b''.join(audio_chunks)
            
        except Exception as e:
            logger.error(f"TTS Error: {e}")
            return b''


# Store active sessions
sessions = {}


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Project Home Voice Interface",
        "endpoints": {
            "websocket": "/ws",
            "socket.io": "/socket.io/"
        }
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for voice communication"""
    await websocket.accept()
    session_id = "default"
    session = VoiceSession(session_id)
    sessions[session_id] = session
    
    try:
        while True:
            # Receive audio data from client
            data = await websocket.receive_bytes()
            
            if not session.is_processing:
                session.is_processing = True
                
                # Process audio in background
                asyncio.create_task(process_voice_turn(websocket, session, data))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    finally:
        if session_id in sessions:
            del sessions[session_id]


async def process_voice_turn(websocket: WebSocket, session: VoiceSession, audio_data: bytes):
    """Process a complete voice interaction turn"""
    try:
        # 1. STT: Audio → Text
        text = await session.process_audio(audio_data)
        if not text:
            await websocket.send_json({"type": "error", "message": "Could not transcribe audio"})
            return
        
        # Send transcription to client
        await websocket.send_json({"type": "transcription", "text": text})
        
        # 2. Get response from Hamm session
        response_text = await session.get_hamm_response(text)
        if not response_text:
            await websocket.send_json({"type": "error", "message": "Could not get response"})
            return
        
        # Send response text to client
        await websocket.send_json({"type": "response", "text": response_text})
        
        # 3. TTS: Text → Audio
        audio_data = await session.generate_speech(response_text)
        if audio_data:
            # Send audio in chunks for streaming
            chunk_size = 4096
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                await websocket.send_bytes(chunk)
        
        # Send completion signal
        await websocket.send_json({"type": "complete"})
        
    except Exception as e:
        logger.error(f"Voice turn error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        session.is_processing = False


# Socket.IO events (alternative to WebSocket)
@sio.event
async def connect(sid, environ):
    logger.info(f"Socket.IO client connected: {sid}")
    session = VoiceSession(sid)
    sessions[sid] = session


@sio.event
async def disconnect(sid):
    logger.info(f"Socket.IO client disconnected: {sid}")
    if sid in sessions:
        del sessions[sid]


@sio.event
async def audio_data(sid, data):
    """Handle audio data from Socket.IO client"""
    if sid not in sessions:
        await sio.emit('error', {'message': 'Session not found'}, to=sid)
        return
    
    session = sessions[sid]
    if session.is_processing:
        await sio.emit('error', {'message': 'Already processing'}, to=sid)
        return
    
    session.is_processing = True
    
    try:
        # Process audio
        text = await session.process_audio(data)
        if text:
            await sio.emit('transcription', {'text': text}, to=sid)
            
            # Get response
            response_text = await session.get_hamm_response(text)
            if response_text:
                await sio.emit('response', {'text': response_text}, to=sid)
                
                # Generate speech
                audio = await session.generate_speech(response_text)
                if audio:
                    # Send audio in chunks
                    chunk_size = 4096
                    for i in range(0, len(audio), chunk_size):
                        chunk = audio[i:i + chunk_size]
                        await sio.emit('audio_chunk', chunk, to=sid)
                    
                    await sio.emit('audio_complete', to=sid)
    
    except Exception as e:
        logger.error(f"Socket.IO processing error: {e}")
        await sio.emit('error', {'message': str(e)}, to=sid)
    finally:
        session.is_processing = False


if __name__ == "__main__":
    # Run with: python main.py
    # Or: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
    uvicorn.run(
        socket_app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )