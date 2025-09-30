# audio.py
import asyncio
import pyaudio

# new

FORMAT = pyaudio.paInt16
CHANNELS = 1 # for Godot
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000 # for Godot
CHUNK_SIZE = 512 

# pya = pyaudio.PyAudio()

class AudioHandler:
    def __init__(self):
        self.pya = pyaudio.PyAudio()
        self.audio_in_queue = None
        self.out_queue = None

        self.receive_audio_task = None
        self.play_audio_task = None

        self.audio_stream = None  # Initialize audio_stream attribute

    async def listen_audio(self):
        print("listening ...")
        mic_info = self.pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            print("Captured audio chunk:", len(data))
            print(self.out_queue.qsize())
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def receive_audio(self, session):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        print("playing ...")
        stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            print("in loop ....")
            bytestream = await self.audio_in_queue.get()
            print(bytestream)
            await asyncio.to_thread(stream.write, bytestream)
            print("playing ..., done")

# old

class AudioHandlerOld:
    def __init__(self):
        self.pya = pyaudio.PyAudio()
        self.audio_out_queue = asyncio.Queue()  # mic → gemini
        self.audio_in_queue = asyncio.Queue()   # gemini → speaker
    
    async def record_microphone(self):
        print("recording ...")
        mic_info = self.pya.get_default_input_device_info()
        stream = self.pya.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        while True:
            data = await asyncio.to_thread(stream.read, CHUNK_SIZE, exception_on_overflow=False)
            await self.audio_out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def play_audio(self):
        print("playing ...")
        stream = self.pya.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
            frames_per_buffer=CHUNK_SIZE,
            
        )
        while True:
            try:
                bytestream = await self.audio_in_queue.get()
                len_byte = len(bytestream)
                print(len_byte, "=== len_byte")
                if bytestream is None:  # special stop marker if ever needed
                    print("playback stopping ...")
                    break
                if bytestream in b"\x00" * len_byte:
                    print("playback stopping ...")
                    break
                stream.write(bytestream)
                
                print(bytestream[:25], type(bytestream), "========== \n\n")
                print("playing ..., done")
            except Exception as e:
                print("playback error:", e)
        await asyncio.sleep(0)   # ✅ yield control so mic/recv tasks continue
        print("playing ..., ddone--====")
