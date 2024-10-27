from collections import OrderedDict
import os
import asyncio
import random
import wave
from discord.ext import commands
from discord.sinks import Sink

# Import the WhisperModel from faster-whisper
from faster_whisper import WhisperModel

# Import Deepgram client
from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions

import io

from utils.plot import generate_voice_response
from utils.synthesis import synthesize_and_stream_audio
from utils.transcript import BOOST_WORDS  # For in-memory byte streams

class UserAudioFiles:
    def __init__(self, user_id, n_channels, sample_rate, loop, model):
        self.sample_rate = sample_rate
        self.n_channels = n_channels
        # create a directory for the user if it doesn't exist
        os.makedirs(f"recordings/{user_id}", exist_ok=True)
        self.user_id = user_id
        file_directory = os.listdir(f"recordings/{user_id}")
        self.latest_file_idx = max(1, len(file_directory) - 2)
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
            if self.latest_file.tell() >= self.sample_rate * 15:
                segments, info = model.transcribe(self.from_index(self.latest_file_idx))
                # save transcript with clip
                with open(f"./recordings/{self.user_id}/{self.latest_file_idx}.txt", "w") as f:
                    for segment in segments:
                        f.write(segment.text)
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


class RealTimeTranscriptionSink(Sink):
    def __init__(self, *, filters=None, transcription_method="deepgram"):
        super().__init__(filters=filters)
        self.loop = asyncio.get_event_loop()
        # print in the loop every frame
        self.n_channels = None
        self.sample_rate = None
        self.transcription_method = transcription_method.lower()
        self.audio_queue = asyncio.Queue()
        self.transcription_task = None
        self.is_running = True
        self.dg_connection = None  # For Deepgram
        self.model = WhisperModel("large-v3", device="cuda", compute_type="float16")
        self.audio_files = {}
        self.running_transcript_chunks = OrderedDict()
        self.interrim_chunk_ids = []
        self.openai_message_history = []
    
    def init(self, vc):
        super().init(vc)
        self.sample_rate = vc.decoder.SAMPLING_RATE
        self.n_channels = vc.decoder.CHANNELS
        print(f"Sample Rate: {self.sample_rate}, Channels: {self.n_channels}")
        self.setup_sink()

    def setup_sink(self):
        for user in os.listdir("recordings"):
            self.audio_files[user] = UserAudioFiles(user, self.n_channels, self.sample_rate, self.loop, self.model)
        if self.transcription_method == "deepgram":
            self.loop.create_task(self.setup_deepgram())
            self.transcription_task = self.loop.create_task(self.transcribe_audio_deepgram())
        elif self.transcription_method == "faster-whisper":
            # Initialize the faster-whisper model
            self.model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            self.transcription_task = self.loop.create_task(self.transcribe_audio_whisper())
        else:
            raise ValueError("Invalid transcription method specified.")

    async def generate_response(self):
        current_transcript = self.get_running_transcript()

        self.openai_message_history.append({"role": "user", "content": current_transcript})
        self.openai_message_history = await generate_voice_response(self.openai_message_history)
        response = self.openai_message_history[-1]["content"]
        print(response)
        # pick a random file and txt pair
        random_user = random.choice(list(self.audio_files.keys()))
        print(random_user)
        random_file_idx = 1
        # make sure both wav and txt exist
        while not os.path.exists(f"recordings/{random_user}/{random_file_idx}.wav") or not os.path.exists(f"recordings/{random_user}/{random_file_idx}.txt"):
            random_file_idx = random.randint(1, len(os.listdir(f"recordings/{random_user}")) - 1)
        print(f"Using {random_user}/{random_file_idx}")
        response = response.replace("BlinkBot:", "")
        self.loop.create_task(synthesize_and_stream_audio(self.vc, response, [f"recordings/{random_user}/{random_file_idx}.wav"], [f"recordings/{random_user}/{random_file_idx}.txt"]))
        # wipe the running transcript chunks
        self.running_transcript_chunks = OrderedDict()
        self.interrim_chunk_ids = []
    
    async def on_utterance_end(self, dg, *args, **kwargs):
        return

    ### Deepgram Setup and Transcription ###
    async def setup_deepgram(self):
        print("Setting up Deepgram transcription.")
        config: DeepgramClientOptions = DeepgramClientOptions(
            options={"keepalive": "true", "timeout": 60000}
        )
        self.deepgram = DeepgramClient(os.getenv("DEEPGRAM_API_TOKEN"), config)
        self.dg_connection = self.deepgram.listen.asyncwebsocket.v("1")

        # Set up event handlers
        self.dg_connection.on(LiveTranscriptionEvents.Open, self.on_open)
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, self.on_message)
        self.dg_connection.on(LiveTranscriptionEvents.Close, self.on_close)
        self.dg_connection.on(LiveTranscriptionEvents.Error, self.on_error)
        self.dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, self.on_utterance_end)
        
        # Start the Deepgram websocket connection
        options: LiveOptions = LiveOptions(
            keywords=BOOST_WORDS,
            model="nova",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            channels=self.n_channels,
            sample_rate=self.sample_rate,
            interim_results=True,
            vad_events=True,
            endpointing=10,
            diarize=True,
        )

        if await self.dg_connection.start(options) is False:
            print("Failed to connect to Deepgram")
            return

        print("Deepgram transcription setup complete.")

    async def transcribe_audio_deepgram(self):
        if (not self.dg_connection.is_connected()):
            return
        print("Deepgram transcription started.")
        has_sent_silence = False
        to_send = b''
        while self.is_running:
            if not self.audio_queue.empty():    
                data = await self.audio_queue.get()
                to_send += data
                if self.dg_connection and len(to_send) >= int(self.sample_rate * 0.5):
                    try:
                        await self.dg_connection.send(data)
                    except Exception as e:
                        print(f"Deepgram Error: {e}")
            else:
                # send 100ms of silence every time it
                if (not has_sent_silence):
                    self.dg_connection.send(b'\x00' * int(self.sample_rate * 0.1))
                    has_sent_silence = True
                self.dg_connection.keep_alive()
                await asyncio.sleep(0.1)

        print("Deepgram transcription stopped.")

    # Event handlers for Deepgram
    async def on_open(self, dg, *args, **kwargs):
        print("Deepgram Connection Open")

    async def on_message(self, dg, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        words_list = result.channel.alternatives[0].words
        words_list.sort(key=lambda x: x.start)
        transcript = ""
        current_speaker = None
        for word in words_list:
            if word.speaker != current_speaker:
                transcript += f"\nSpeaker {word.speaker}: "
                current_speaker = word.speaker
            transcript += f"{word.punctuated_word} "
        if len(sentence) == 0:
            return
        if result.is_final:
            if result.start in self.interrim_chunk_ids:
                # print(f"Replacing interim chunk {self.running_transcript_chunks[result.metadata.request_id]} with {transcript}")
                self.running_transcript_chunks[result.start] = transcript
            else:
                self.running_transcript_chunks[result.start] = transcript
        else:
            print(f"Interim chunk {result.start}")
            self.running_transcript_chunks[result.start] = transcript
            self.interrim_chunk_ids.append(result.start)
        if result.speech_final:
            await self.generate_response()
    
    def get_running_transcript(self):
        return "".join(self.running_transcript_chunks.values())

    async def on_close(self, dg, *args, **kwargs):
        print("Deepgram Connection Closed")

    async def on_error(self, dg, error, **kwargs):
        print(f"Deepgram Error: {error}")

    ### Faster-Whisper Transcription ###
    async def transcribe_audio_whisper(self):
        print("Whisper transcription started.")

        chunk_length_s = 10  # Duration of each audio chunk in seconds
        stream_chunk_s = 3  # Process every 0.5 seconds
        stride_length_s = (1,1)  # Overlap of 1 second on each side

        size_of_sample = 2  # Since we're using int16 (2 bytes per sample)
        channels = self.n_channels

        # Calculate sizes in bytes
        chunk_size_bytes = int(self.sample_rate * chunk_length_s * channels * size_of_sample)
        stream_chunk_size_bytes = int(self.sample_rate * stream_chunk_s * channels * size_of_sample)
        stride_left_bytes = int(self.sample_rate * stride_length_s[0] * channels * size_of_sample)
        stride_right_bytes = int(self.sample_rate * stride_length_s[1] * channels * size_of_sample)

        # Total size of chunk including strides
        total_chunk_size_bytes = stride_left_bytes + chunk_size_bytes + stride_right_bytes

        buffer = b''

        # Prepend zeros to the buffer to handle the initial left stride
        buffer += b'\x00' * stride_left_bytes

        while self.is_running:
            # Collect data from the audio queue
            data = await self.audio_queue.get()
            if data is None:
                break

            # Append data to the buffer
            buffer += data

            buffer_file = wave.open("buffer.wav", "wb")
            buffer_file.setnchannels(self.n_channels)
            buffer_file.setsampwidth(size_of_sample)
            buffer_file.setframerate(self.sample_rate)
            buffer_file.writeframes(buffer)
            buffer_file.close()

            # Process the buffer if we have enough bytes
            while len(buffer) >= total_chunk_size_bytes:
                # Extract the chunk with strides
                chunk_with_strides = buffer[:total_chunk_size_bytes]

                # Remove the processed part from the buffer, advance by stream_chunk_size_bytes
                buffer = buffer[stream_chunk_size_bytes:]

                # Create an in-memory byte stream
                audio_stream = io.BytesIO(chunk_with_strides)

                chunked_file = wave.open("chunked.wav", "wb")
                chunked_file.setnchannels(self.n_channels)
                chunked_file.setsampwidth(size_of_sample)
                chunked_file.setframerate(self.sample_rate)
                chunked_file.writeframes(chunk_with_strides)
                chunked_file.close()

                # Transcribe using faster-whisper
                segments, _ = self.model.transcribe(
                    "chunked.wav",
                    language="en",
                    beam_size=5,
                    without_timestamps=True,
                )

                transcript = "".join([segment.text for segment in segments])

                if transcript.strip():
                    print(f"Whisper Transcription: {transcript}")

        print("Whisper transcription stopped.")

    ### Write Method ###
    def write(self, data, user):
        if (self.n_channels or self.sample_rate) is None:
            return

        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, data)
        if user not in self.audio_files:
            self.audio_files[user] = UserAudioFiles(user, self.n_channels, self.sample_rate, self.loop, self.model)
        self.audio_files[user].write(data)

    ### Cleanup Method ###
    def cleanup(self):
        super().cleanup()
        self.is_running = False
        if self.transcription_task:
            self.transcription_task.cancel()

        # Signal the audio queue to stop by putting None into it
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, None)

        if self.transcription_method == "deepgram":
            # Wait for the Deepgram connection to close
            if self.dg_connection:
                self.loop.create_task(self.dg_connection.finish())

        print("Cleanup complete.")