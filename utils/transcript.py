import os
import time
from deepgram import FileSource
import httpx

BOOST_WORDS = ["Reyna", "Nayo", "Sage", "Killjoy", "Viper", "Raze", "Skye", "Cypher", "Sova", "Brimstone", "Phoenix", "KAY/O", "Chamber", "Neon", "Fade", "Deadlock", "Pramit", "Jon", "Lucy", "Kwon"]

def replace_usernames(transcript):
    username_mapping = {
        "Pramit Pegger": "Kwon",
        "juju": "Jon",
        "0ptimize": "Jimmy",
        "01june": "Lucy",
        "/": "Pramit",
        "koko": "Lily",
    }
    for name in username_mapping:
        transcript = transcript.replace(name, username_mapping[name])
    return transcript

async def transcribe_audio(sink, deepgram, options):

    words_list = []
    for user_id, audio in sink.audio_data.items():
        audio_data = audio.file.read()
        payload: FileSource = {"buffer": audio_data}

        os.makedirs(f"audio/{user_id}", exist_ok=True)
        with open(f"audio/{user_id}/{user_id}_{time.time()}.wav", "wb") as f:
            f.write(audio_data)

        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options, timeout=httpx.Timeout(300.0, connect=10))
        words = response["results"]["channels"][0]["alternatives"][0]["words"]
        words = [word.to_dict() for word in words]

        for word in words:
            new_word = {
                "word": word["word"],
                "start": word["start"],
                "end": word["end"],
                "confidence": word["confidence"],
                "punctuated_word": word["punctuated_word"],
                "speaker": user_id,
                "speaker_confidence": word["speaker_confidence"],
            }
            words_list.append(new_word)
    
    words_list.sort(key=lambda x: x["start"])
    return words_list