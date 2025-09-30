# main.py (backend)
import asyncio
import json
import base64
import wave
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Optional
from session_manager import SessionManager
import time

app = FastAPI()

class ClientSession:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.session_manager: Optional[SessionManager] = None
        self.mode: Optional[str] = None
        self.gemini_audio_task: Optional[asyncio.Task] = None
        self.expecting_audio_data = False
        self.audio_length = 0
        self.last_audio_time = time.time()

active_sessions: Dict[str, ClientSession] = {}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    client_id = f"{websocket.client.host}:{websocket.client.port}"
    session = ClientSession(websocket)
    active_sessions[client_id] = session
    
    print(f"✅ Client connected: {client_id}")

    # Create concurrent tasks for handling different message types
    receive_task = asyncio.create_task(receive_messages(session, websocket))
    
    try:
        await receive_task
    except WebSocketDisconnect:
        print(f"❌ Client disconnected: {client_id}")
    except Exception as e:
        print(f"⚠️ Error in websocket: {e}")
        import traceback
        traceback.print_exc()
    finally:
        receive_task.cancel()
        await cleanup_session(session)
        del active_sessions[client_id]


async def receive_messages(session: ClientSession, websocket: WebSocket):
    """Receive messages with minimal blocking"""
    while True:
        message = await websocket.receive()
        
        # Handle messages in background tasks to avoid blocking
        if "text" in message and message["text"]:
            asyncio.create_task(handle_json_message(session, message["text"]))
            
        elif "bytes" in message and message["bytes"]:
            if session.expecting_audio_data:
                asyncio.create_task(handle_audio_data(session, message["bytes"]))
                session.expecting_audio_data = False


async def handle_json_message(session: ClientSession, message_text: str):
    """Handle JSON messages from client"""
    try:
        data = json.loads(message_text)
        msg_type = data.get("type")
        
        if msg_type == "audio":
            # Audio header - expect binary data next
            session.expecting_audio_data = True
            session.audio_length = data.get("length", 0)
            
        elif msg_type == "screen":
            # Don't block - process in background
            await ensure_session_mode(session, "screen")
            await handle_screen_frame(session, data)
            
        elif msg_type == "video":
            await ensure_session_mode(session, "camera")
            await handle_video_frame(session, data)
            
    except Exception as e:
        print(f"Error handling JSON message: {e}")


async def ensure_session_mode(session: ClientSession, required_mode: str):
    """Ensure session is in the correct mode"""
    mode_map = {
        "audio": "audio",
        "screen": "screen",
        "camera": "video",
        "video": "video"
    }
    
    backend_mode = mode_map.get(required_mode, required_mode)
    
    # Start session if not exists
    if not session.session_manager:
        await start_session(session, backend_mode)
    elif session.mode != backend_mode and backend_mode in ["screen", "video"]:
        # Just update mode for visual modes
        session.mode = backend_mode
        if hasattr(session.session_manager, 'video'):
            session.session_manager.video.video_mode = backend_mode


async def handle_audio_data(session: ClientSession, audio_data: bytes):
    """Handle incoming audio data with minimal latency"""
    if not session.session_manager:
        await ensure_session_mode(session, "audio")
    
    if session.session_manager:
        # Track audio timing for debugging
        current_time = time.time()
        time_since_last = current_time - session.last_audio_time
        session.last_audio_time = current_time
        
        await session.session_manager.enqueue_audio(audio_data)
        print(f"🎤 Audio chunk: {len(audio_data)} bytes (interval: {time_since_last:.3f}s)")


async def handle_screen_frame(session: ClientSession, data: dict):
    """Handle screen capture frames without blocking audio"""
    if session.session_manager:
        frame_data = {
            "mime_type": data.get("mime_type", "image/jpeg"),
            "data": data.get("data")
        }
        # Don't await - let it process in background
        asyncio.create_task(session.session_manager.enqueue_video(frame_data))
        print(f"🖥️ Screen frame received")


async def handle_video_frame(session: ClientSession, data: dict):
    """Handle video frames without blocking audio"""
    if session.session_manager:
        frame_data = {
            "mime_type": data.get("mime_type", "image/jpeg"),
            "data": data.get("data")
        }
        asyncio.create_task(session.session_manager.enqueue_video(frame_data))
        print(f"📹 Video frame received")


async def start_session(session: ClientSession, mode: str):
    """Start a new session with given mode"""
    if session.session_manager:
        await cleanup_session(session)
    
    video_mode_map = {
        "audio": "none",
        "screen": "screen",
        "video": "camera",
        "camera": "camera"
    }
    video_mode = video_mode_map.get(mode, "none")
    
    # Create session manager with optimized settings
    session.session_manager = SessionManager(mode=video_mode)
    session.mode = mode
    
    # Start the Gemini session
    asyncio.create_task(session.session_manager.run())
    
    # Start high-priority audio sender
    session.gemini_audio_task = asyncio.create_task(
        send_gemini_audio_to_client(session)
    )
    
    print(f"🚀 Started {mode} session")


async def send_gemini_audio_to_client(session: ClientSession):
    """Send audio from Gemini back to client with minimal latency"""
    try:
        while session.session_manager:
            try:
                # Don't use timeout - just check if queue has items
                if not session.session_manager.audio.audio_in_queue.empty():
                    audio_data = await session.session_manager.audio.audio_in_queue.get()
                    
                    if isinstance(audio_data, (bytes, bytearray, memoryview)):
                        await session.websocket.send_bytes(bytes(audio_data))
                        print(f"🔊 Sent audio to client: {len(audio_data)} bytes")
                else:
                    # Very short sleep to keep loop responsive
                    await asyncio.sleep(0.001)
                    
            except Exception as e:
                print(f"Error in audio send: {e}")
                await asyncio.sleep(0.01)
                
    except asyncio.CancelledError:
        print("Audio sender cancelled")


async def cleanup_session(session: ClientSession):
    """Clean up session resources"""
    if session.gemini_audio_task:
        session.gemini_audio_task.cancel()
        try:
            await session.gemini_audio_task
        except asyncio.CancelledError:
            pass
    
    session.session_manager = None
    session.mode = None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)