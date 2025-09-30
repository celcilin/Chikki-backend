# gemini_client.py
from google import genai
from google.genai import types
import os

# new
API_KEY = "AIzaSyAHLpftnNm7FPCA-ff-Q0dGCIRFHLkAveY"
MODEL = "models/gemini-2.5-flash-live-preview"

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=API_KEY,
)

CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "AUDIO",
    ],
    media_resolution="MEDIA_RESOLUTION_LOW",
    speech_config=types.SpeechConfig(
        language_code="en-US",
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
        )
    ),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
)

class GeminiClient:
    def __init__(self):
        self.client = client

    def connect(self):
        """Return async context manager for Gemini Live session"""
        return self.client.aio.live.connect(model=MODEL, config=CONFIG)

    # async def send(self, session, data, end_of_turn=False):
    #     if isinstance(data, str):
    #         await session.send(input={"text": data}, end_of_turn=end_of_turn)
    #     else:
    #         await session.send(input=data, end_of_turn=end_of_turn)

    # async def receive(self, session):
    #     async for response in session.receive():
    #         yield response