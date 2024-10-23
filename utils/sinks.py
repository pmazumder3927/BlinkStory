import os
import asyncio
import numpy as np
from discord.ext import commands
from discord.sinks import Sink

# Import the WhisperModel from faster-whisper
from faster_whisper import WhisperModel

# Import Deepgram client
from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions

class RealTimeTranscriptionSink(Sink):
    def __init__(self, *, filters=None, transcription_method="deepgram"):
        super().__init__(filters=filters)
        self.loop = asyncio.get_event_loop()
        self.n_channels = None
        self.sample_rate = None
        self.transcription_method = transcription_method.lower()
        self.audio_buffer = b''
        self.buffer_lock = asyncio.Lock()
        self.transcription_task = None
        self.is_running = True
        self.audio_queue = asyncio.Queue()
        self.dg_connection = None  # For Deepgram
        self.model = None          # For faster-whisper

    def init(self, vc):
        super().init(vc)
        self.sample_rate = vc.decoder.SAMPLING_RATE
        self.n_channels = vc.decoder.CHANNELS
        print(f"Sample Rate: {self.sample_rate}, Channels: {self.n_channels}")
        self.setup_sink()

    def setup_sink(self):
        if self.transcription_method == "deepgram":
            self.loop.create_task(self.setup_deepgram())
            self.transcription_task = self.loop.create_task(self.transcribe_audio_deepgram())
        elif self.transcription_method == "faster-whisper":
            # Initialize the faster-whisper model
            self.model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            self.transcription_task = self.loop.create_task(self.transcribe_audio_whisper())
        else:
            raise ValueError("Invalid transcription method specified.")

    ### Deepgram Setup and Transcription ###
    async def setup_deepgram(self):
        print("Setting up Deepgram transcription.")
        config: DeepgramClientOptions = DeepgramClientOptions(
            options={"keepalive": "true"}
        )
        self.deepgram = DeepgramClient(os.getenv("DEEPGRAM_API_TOKEN"), config)
        self.dg_connection = self.deepgram.listen.asyncwebsocket.v("1")

        # Set up event handlers
        self.dg_connection.on(LiveTranscriptionEvents.Open, self.on_open)
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, self.on_message)
        self.dg_connection.on(LiveTranscriptionEvents.Close, self.on_close)
        self.dg_connection.on(LiveTranscriptionEvents.Error, self.on_error)
        
        # Start the Deepgram websocket connection
        options: LiveOptions = LiveOptions(
            model="nova",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            channels=self.n_channels,
            sample_rate=self.sample_rate,
            interim_results=True,
            utterance_end_ms=1000,
            vad_events=True,
            endpointing=300,
        )

        if await self.dg_connection.start(options) is False:
            print("Failed to connect to Deepgram")
            return

        print("Deepgram transcription setup complete.")

    async def transcribe_audio_deepgram(self):
        print("Deepgram transcription started.")
        while self.is_running:
            data = await self.audio_queue.get()
            if data is None:
                break
            if self.dg_connection:
                await self.dg_connection.send(data)

        print("Deepgram transcription stopped.")

    # Event handlers for Deepgram
    async def on_open(self, dg, *args, **kwargs):
        print("Deepgram Connection Open")

    async def on_message(self, dg, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if len(sentence) == 0:
            return
        if result.is_final:
            print(f"Deepgram Transcription: {sentence}")
        else:
            print(f"Deepgram Interim Transcription: {sentence}")

    async def on_close(self, dg, *args, **kwargs):
        print("Deepgram Connection Closed")

    async def on_error(self, dg, error, **kwargs):
        print(f"Deepgram Error: {error}")

    ### Faster-Whisper Transcription ###
    async def transcribe_audio_whisper(self):
        print("Whisper transcription started.")

        chunk_length_s = 10  # Duration of each audio chunk in seconds
        stream_chunk_s = 2  # Process every 2 seconds
        stride_length_s = (1.0, 1.0)  # Overlap of 1 second on each side

        size_of_sample = 2  # Since we're using int16 (2 bytes per sample)
        channels = self.n_channels

        # Calculate sizes in bytes
        chunk_size = int(self.sample_rate * chunk_length_s * channels * size_of_sample)
        stream_chunk_size = int(self.sample_rate * stream_chunk_s * channels * size_of_sample)
        stride_left_size = int(self.sample_rate * stride_length_s[0] * channels * size_of_sample)
        stride_right_size = int(self.sample_rate * stride_length_s[1] * channels * size_of_sample)

        buffer = b''

        while self.is_running:
            await asyncio.sleep(stream_chunk_s)
            async with self.buffer_lock:
                if not self.audio_buffer:
                    continue
                buffer += self.audio_buffer
                self.audio_buffer = b''

            while len(buffer) >= chunk_size:
                # Extract the chunk to process
                chunk = buffer[:chunk_size]
                buffer = buffer[stream_chunk_size:]

                # Apply strides (overlaps)
                left_stride = buffer[:stride_left_size] if len(buffer) >= stride_left_size else buffer
                right_stride = buffer[:stride_right_size] if len(buffer) >= stride_right_size else buffer

                # Combine strides and chunk
                chunk_with_strides = left_stride + chunk + right_stride

                # Convert bytes to numpy array
                audio_array = np.frombuffer(chunk_with_strides, np.int16).astype(np.float32) / 32768.0

                # Transcribe using faster-whisper
                segments, _ = self.model.transcribe(
                    audio_array,
                    language="en",
                    beam_size=5,
                    without_timestamps=True
                )

                transcript = "".join([segment.text for segment in segments])

                if transcript.strip():
                    print(f"Whisper Transcription: {transcript}")

        print("Whisper transcription stopped.")

    ### Write Method ###
    def write(self, data, user):
        if (self.n_channels or self.sample_rate) is None:
            return

        if self.transcription_method == "deepgram":
            # Put the data into the audio queue for Deepgram
            self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, data)
        elif self.transcription_method == "faster-whisper":
            # Buffer the audio data for faster-whisper
            async def buffer_audio():
                async with self.buffer_lock:
                    self.audio_buffer += data
            self.loop.create_task(buffer_audio())

    ### Cleanup Method ###
    def cleanup(self):
        super().cleanup()
        self.is_running = False
        if self.transcription_task:
            self.transcription_task.cancel()

        if self.transcription_method == "deepgram":
            # Signal the transcription task to exit
            self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, None)
            # Wait for the Deepgram connection to close
            if self.dg_connection:
                self.loop.create_task(self.dg_connection.finish())
        print("Cleanup complete.")
