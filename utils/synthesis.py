import random
import wave
from discord import FFmpegPCMAudio
import pyaudio
import requests
import ormsgpack
from pydub import AudioSegment
from tools.commons import ServeReferenceAudio, ServeTTSRequest
from tools.file import audio_to_bytes, read_ref_text


async def synthesize_and_stream_audio(vc, text, reference_audio, reference_text, api_key="YOUR_API_KEY"):
    # Process reference audio and text
    byte_audios = [audio_to_bytes(ref_audio) for ref_audio in reference_audio] if reference_audio else []
    ref_texts = [read_ref_text(ref_text) for ref_text in reference_text] if reference_text else []
    
    data = {
        "text": text,
        "references": [
            ServeReferenceAudio(audio=ref_audio, text=ref_text)
            for ref_text, ref_audio in zip(ref_texts, byte_audios)
        ],
        "streaming": True,
        "format": "wav",
    }

    pydantic_data = ServeTTSRequest(**data)

    response = requests.post(
        "http://127.0.0.1:8080/v1/tts",
        data=ormsgpack.packb(pydantic_data, option=ormsgpack.OPT_SERIALIZE_PYDANTIC),
        stream=True,
        headers={
            "authorization": f"Bearer {api_key}",
            "content-type": "application/msgpack",
        },
    )

    if response.status_code == 200:
        audio_format = pyaudio.paInt16  # Assuming 16-bit PCM format
        temp_filename = f"temp{random.randint(0, 1000000)}.wav"
        test_wav = wave.open(temp_filename, "wb")
        test_wav.setnchannels(1)
        test_wav.setsampwidth(2)
        test_wav.setframerate(44100)
        test_wav.writeframes(response.content)
        test_wav.close()
        vc.play(FFmpegPCMAudio(temp_filename))

        # wf = pyaudio.PyAudio()
        # stream = wf.open(format=audio_format, channels=1, rate=44100, output=True)

        # # Play the audio stream in Discord VC
        # try:
        #     for chunk in response.iter_content(chunk_size=1024):
        #         if chunk:
        #             # stream.write(chunk)
        #             # turn 44100 1 channel to 48000 2 channel
        #             audio_segment = AudioSegment.from_raw(chunk, sample_width=2, frame_rate=44100, channels=1)
        #             audio_segment = audio_segment.set_frame_rate(48000).set_sample_width(2).set_channels(2)
        #             # save segment
        #             audio_segment.export("temp.wav", format="wav")
        #             vc.send_audio_packet(audio_segment.raw_data, encode=True)
        # finally:
        #     stream.stop_stream()
        #     stream.close()
        #     wf.terminate()
    else:
        print(f"Request failed with status code {response.status_code}")
        print(response.json())