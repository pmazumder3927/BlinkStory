import os
import wave
from discord.ext import commands
from discord.sinks import Sink
from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions
import asyncio

class UserAudioFiles:
    def __init__(self, user_id, n_channels, sample_rate, loop):
        self.sample_rate = sample_rate
        self.n_channels = n_channels
        # create a directory for the user if it doesn't exist
        os.makedirs(f"recordings/{user_id}", exist_ok=True)
        self.user_id = user_id
        file_directory = os.listdir(f"recordings/{user_id}")
        self.latest_file_idx = max(1, len(file_directory) - 1)
        latest_file = wave.open(self.from_index(self.latest_file_idx), 'wb')
        latest_file.setnchannels(n_channels)
        latest_file.setsampwidth(2)
        latest_file.setframerate(sample_rate)

        self.latest_file = latest_file
        self.write_queue = asyncio.Queue()
        self.loop = loop
        self.loop.create_task(self.manage_files())

    def from_index(self, idx):
        return f"recordings/{self.user_id}/{idx}.wav"

    def strip_leading_silence(self, data):
        # Strip only the leading silence and return the rest of the data
        silence_chunk_size = 2  # Since we're using 16-bit samples, each sample is 2 bytes
        idx = 0
        while idx < len(data) - silence_chunk_size:
            # Check 2 bytes at a time for leading silence
            if data[idx:idx+silence_chunk_size] != b'\x00\x00':
                self.stripped_leading_silence = True  # Stop stripping silence after finding sound
                return data[idx:]
            idx += silence_chunk_size
        return b''  # If the entire data chunk is silence, return empty

    async def manage_files(self):
        while True:
            await asyncio.sleep(1)
            if self.write_queue.qsize() > 0:
                # current clip length
                current_length = self.latest_file.tell()
                data = b''
                while not self.write_queue.empty():
                    data += await self.write_queue.get()
                data = self.strip_leading_silence(data)
                self.latest_file.writeframes(data)
            print(self.latest_file.tell())
            if self.latest_file.tell() >= self.sample_rate * 15:
                self.latest_file_idx += 1
                self.latest_file = self.prep_new_file(self.from_index(self.latest_file_idx))
    def prep_new_file(self, dir):
        new_file = wave.open(dir, 'wb')
        new_file.setnchannels(self.n_channels)
        new_file.setsampwidth(2)
        new_file.setframerate(self.sample_rate)
        return new_file
    def write(self, data):
        self.loop.call_soon_threadsafe(self.write_queue.put_nowait, data)

class DeepgramSink(Sink):
    def __init__(self, *, filters=None):
        super().__init__(filters=filters)
        self.audio_queue = asyncio.Queue()
        self.loop = asyncio.get_event_loop()
        self.dg_connection = None
        self.n_channels = None
        self.sample_rate = None
        self.audio_files = {}

    def init(self, vc):
        super().init(vc)
        self.sample_rate = vc.decoder.SAMPLING_RATE
        self.n_channels = vc.decoder.CHANNELS
        print(f"Sample Rate: {self.sample_rate}, Channels: {self.n_channels}")
        self.setup_sink()

    def setup_sink(self):
        self.loop.create_task(self.setup_deepgram())
        self.deepgram_task = self.loop.create_task(self.transcribe_audio())
        for directory in os.listdir("recordings"):
            self.audio_files[directory] = UserAudioFiles(directory, self.n_channels, self.sample_rate, self.loop)

    async def setup_deepgram(self):
        # Initialize Deepgram client
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
            model="nova-2",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            channels=self.n_channels,
            sample_rate=self.sample_rate,
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
            endpointing=300,
        )

        if await self.dg_connection.start(options) is False:
            print("Failed to connect to Deepgram")
            return

    async def transcribe_audio(self):
        while True:
            data = await self.audio_queue.get()
            if data is None:
                break
            if self.dg_connection:
                res = await self.dg_connection.send(data)

    def write(self, data, user):
        # In the write method, we receive audio data chunks
        # We'll put the data into the audio queue to be sent to Deepgram
        # Note: data is in bytes
        if (self.n_channels or self.sample_rate) is None:
            return
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, data)
        if not user in self.audio_files:
            self.audio_files[user] = UserAudioFiles(user, self.n_channels, self.sample_rate, self.loop)
        self.audio_files[user].write(data)
    
    def cleanup(self):
        super().cleanup()
        # Signal the transcribe_audio task to exit
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, None)
        # Wait for the Deepgram connection to close
        if self.dg_connection:
            self.loop.create_task(self.dg_connection.finish())

    # Event handlers for Deepgram
    async def on_open(self, dg, *args, **kwargs):
        print("Deepgram Connection Open")

    async def on_message(self, dg, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if len(sentence) == 0:
            return
        if result.is_final:
            print(f"Transcription: {sentence}")
        else:
            print(f"Interim Transcription: {sentence}")

    async def on_close(self, dg, *args, **kwargs):
        print("Deepgram Connection Closed")

    async def on_error(self, dg, error, **kwargs):
        print(f"Deepgram Error: {error}")