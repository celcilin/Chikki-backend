# session_manager.py
import asyncio
import traceback
from gemini_client import GeminiClient
from audio import AudioHandler
from video import VideoHandler

class SessionManager:
    def __init__(self, mode="none"):
        self.gemini = GeminiClient()
        self.audio = AudioHandler()
        self.video = VideoHandler(mode)
        self.text = TextHandler()
        self.session = None
        
        # Flags to control what data sources to use
        self.use_frontend_video = True  # Use video from frontend instead of local capture
        self.use_frontend_audio = True  # Use audio from frontend instead of local capture

        # OPTIMIZATION 1: Larger queue sizes for better buffering
        self.audio.audio_in_queue = asyncio.Queue(maxsize=50)  # Increased for smooth playback
        self.audio.out_queue = asyncio.Queue(maxsize=20)       # Increased for audio buffering
        self.video.out_queue = asyncio.Queue(maxsize=10)       # Reasonable size for video
    
    async def run(self):
        try:
            async with (
                self.gemini.connect() as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                # OPTIMIZATION 2: Split send_realtime into separate audio/video tasks
                tg.create_task(self._send_audio_priority())
                tg.create_task(self._send_video_background())
                
                # Only start local capture if not using frontend data
                if not self.use_frontend_video:
                    if self.video.video_mode == "camera":
                        tg.create_task(self.video.get_frames())
                    elif self.video.video_mode == "screen":
                        tg.create_task(self.video.get_screen())
                
                if not self.use_frontend_audio:
                    tg.create_task(self.audio.listen_audio())

                # CHANGE 2: Replace receive_from_gemini with receive_audio
                tg.create_task(self.receive_audio())
                
                # CHANGE 3: Add play_audio task - UNCOMMENTED for actual playback
                # tg.create_task(self.audio.play_audio())
                
                # Keep running
                await asyncio.Event().wait()

        except asyncio.CancelledError:
            print("Session cancelled")
        except ExceptionGroup as eg:  # CHANGE 4: Handle ExceptionGroup like reference
            print("Session error - ExceptionGroup:")
            traceback.print_exception(eg)
            if hasattr(self.audio, 'audio_stream') and self.audio.audio_stream:
                self.audio.audio_stream.close()
        except Exception as e:
            print(f"Session error: {e}")
            traceback.print_exc()

    # OPTIMIZATION 3: Split into high-priority audio and low-priority video
    async def _send_audio_priority(self):
        """High-priority audio sender - no timeouts for minimal latency"""
        consecutive_packets = 0
        while True:
            try:
                msg = await self.audio.out_queue.get()  # No timeout - wait for audio
                await self.session.send(input=msg)
                
                consecutive_packets += 1
                # Batch logging to reduce overhead
                if consecutive_packets % 10 == 0:
                    print(f"→ Sent {consecutive_packets} audio packets")
                    consecutive_packets = 0
                    
            except Exception as e:
                print(f"Error sending audio: {e}")
                await asyncio.sleep(0.001)

    async def _send_video_background(self):
        """Background video sender - lower priority than audio"""
        while True:
            try:
                # Use short timeout to not block too long
                frame = await asyncio.wait_for(self.video.out_queue.get(), timeout=0.05)
                await self.session.send(input=frame)
                print(f"→ Sent {frame['mime_type']} to Gemini")
            except asyncio.TimeoutError:
                # No video available, yield to other tasks
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"Error sending video: {e}")
                await asyncio.sleep(0.1)

    # Keep original method for compatibility but mark as deprecated
    async def send_realtime(self):
        """[DEPRECATED] Use _send_audio_priority and _send_video_background instead"""
        await asyncio.gather(
            self._send_audio_priority(),
            self._send_video_background()
        )

    # OPTIMIZATION 4: Improved receive with overflow protection
    async def receive_audio(self):
        """Background task to read from websocket and write pcm chunks to output queue"""
        packets_received = 0
        while True:
            try:
                # Get a turn from the session
                turn = self.session.receive()
                async for response in turn:
                    # Handle audio data
                    if data := response.data:
                        # OPTIMIZATION 5: Use put_nowait with overflow protection
                        try:
                            self.audio.audio_in_queue.put_nowait(data)
                            packets_received += 1
                            
                            if packets_received % 10 == 0:
                                print(f"← Received {packets_received} audio packets from Gemini")
                                packets_received = 0
                                
                        except asyncio.QueueFull:
                            # Drop oldest packet to maintain real-time performance
                            try:
                                self.audio.audio_in_queue.get_nowait()
                                self.audio.audio_in_queue.put_nowait(data)
                                print("⚠️ Audio playback queue full, dropped oldest packet")
                            except:
                                pass
                        continue
                    
                    # Handle text responses
                    if text := response.text:
                        print(f"← Gemini: {text}")

                # Turn complete - clear audio queue for interruptions
                print("--- Turn Complete ---")
                # OPTIMIZATION 6: More efficient queue clearing
                cleared = 0
                while not self.audio.audio_in_queue.empty():
                    try:
                        self.audio.audio_in_queue.get_nowait()
                        cleared += 1
                    except:
                        break
                if cleared > 0:
                    print(f"Cleared {cleared} packets for interruption")
                    
            except Exception as e:
                print(f"Error receiving from Gemini: {e}")
                await asyncio.sleep(0.1)

    # OPTIMIZATION 7: Add overflow protection for enqueue methods
    async def enqueue_audio(self, data: bytes):
        """Called by websocket to push raw PCM audio from frontend"""
        audio_packet = {
            "data": data, 
            "mime_type": "audio/pcm"
        }
        
        try:
            # Try non-blocking put first
            self.audio.out_queue.put_nowait(audio_packet)
        except asyncio.QueueFull:
            # Queue full - drop oldest and add new
            try:
                self.audio.out_queue.get_nowait()
                self.audio.out_queue.put_nowait(audio_packet)
                print("⚠️ Audio out queue full, dropped oldest packet")
            except:
                # If all else fails, use blocking put
                await self.audio.out_queue.put(audio_packet)

    async def enqueue_video(self, data: dict):
        """Called by websocket to push video/screen frames from frontend"""
        # Validate frame data
        if "mime_type" in data and "data" in data:
            try:
                # Try non-blocking put first
                self.video.out_queue.put_nowait(data)
            except asyncio.QueueFull:
                # Queue full - drop oldest frame
                try:
                    self.video.out_queue.get_nowait()
                    self.video.out_queue.put_nowait(data)
                    print("⚠️ Video queue full, dropped oldest frame")
                except:
                    # Skip this frame if we can't add it
                    print("⚠️ Video queue blocked, skipping frame")
        else:
            print(f"⚠️ Invalid video frame format: {data.keys()}")


class TextHandler:
    """Handle text interactions (for testing)"""
    def __init__(self):
        pass

    async def send_text(self, session):
        while True:
            text = await asyncio.to_thread(input, "message > ")
            if text.lower() == "q":
                break
            await session.send(input=text or ".", end_of_turn=True)