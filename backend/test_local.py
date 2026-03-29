"""
Test script for local development
"""

import asyncio
import websockets
import json
import wave
import io

async def test_websocket():
    uri = "ws://localhost:8000/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            
            # Send a test audio message (empty for now)
            test_audio = b"test"  # In real usage, this would be actual audio data
            await websocket.send(test_audio)
            
            # Listen for responses
            while True:
                message = await websocket.recv()
                
                if isinstance(message, str):
                    # JSON message
                    data = json.loads(message)
                    print(f"Received: {data}")
                    
                    if data.get("type") == "complete":
                        break
                else:
                    # Binary audio data
                    print(f"Received audio chunk: {len(message)} bytes")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())