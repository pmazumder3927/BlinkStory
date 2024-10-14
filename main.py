from aiohttp import ClientSession
import discord
import openai
from dotenv import load_dotenv
from os import environ as env
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
import asyncio
import requests
import json
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.loop import loop

bot = discord.Bot()
connections = {}
load_dotenv()

deepgram = DeepgramClient(env.get("DEEPGRAM_API_TOKEN"))

options = PrerecordedOptions(
    model="nova-2",
    smart_format=True,
    utterances=True,
    punctuate=True,
    diarize=True,
    detect_language=True,
)

client = openai.OpenAI(
    api_key=env.get("OPENAI_API_KEY")
)

VIDEO_API_URL = "https://api.useapi.net/v1/minimax/videos/create"
VIDEO_API_TOKEN = env.get("VIDEO_API_TOKEN")
SONG_API_URL = "https://api.goapi.ai/api/suno/v1/music"
SONG_API_TOKEN = env.get("GHETTO_API_TOKEN")

def create_request(url, headers, body=None, params=None, method="post"):
    if method == "post":
        response = requests.post(url, headers=headers, data=json.dumps(body))
    elif method == "get":
        response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error with request to {url}: {response.status_code}, {response.text}")
        return None

def create_video_request(scene_prompt, scene_number):
    headers = {
        "Authorization": f"Bearer {VIDEO_API_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "prompt": scene_prompt,
        "promptOptimization": True,
        "replyRef": f"Scene_{scene_number}",
        "maxJobs": 5
    }
    response = create_request(VIDEO_API_URL, headers, body=body)
    return response.get("videoId") if response else None

def create_song_request(lyrics):
    headers = {
        "X-API-Key": SONG_API_TOKEN,
        "Content-Type": "application/json"
    }
    body = {
        "custom_mode": True,
        "mv": "chirp-v3-5",
        "input": {
            "prompt": lyrics,
            "title": "Electric Dreams",
            "continue_at": 0,
            "continue_clip_id": ""
        }
    }
    response = create_request(SONG_API_URL, headers, body=body)
    return response.get("data", {}).get("task_id") if response else None



@bot.command()
async def record(ctx):
    voice = ctx.author.voice

    if not voice:
        await ctx.respond("⚠️ You aren't in a voice channel!")
        return

    vc = await voice.channel.connect()
    connections.update({ctx.guild.id: vc})

    vc.start_recording(
        discord.sinks.WaveSink(),
        once_done,
        ctx.channel,
    )
    await ctx.respond("🔴 Listening to this conversation.")

async def once_done(sink: discord.sinks, channel: discord.TextChannel, *args):
    recorded_users = {user_id: await channel.guild.fetch_member(user_id) for user_id in sink.audio_data.keys()}
    await sink.vc.disconnect()

    words_list = []

    for user_id, audio in sink.audio_data.items():
        payload: FileSource = {
            "buffer": audio.file.read(),
        }

        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)

        words = response["results"]["channels"][0]["alternatives"][0]["words"]
        words = [word.to_dict() for word in words]

        for word in words:
            if word["speaker"] != 0:
                user_id = word["speaker"]

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
    transcript = ""
    current_speaker = None

    for word in words_list:
        if "speaker" in word and word["speaker"] != current_speaker:
            speaker_name = recorded_users[word["speaker"]].display_name
            transcript += f"\n\nSpeaker {speaker_name}: "
            current_speaker = word["speaker"]
        transcript += f"{word['punctuated_word']} "

    transcript = transcript.strip()

    # if transcript is too short, don't generate a music video
    if len(transcript) < 100:
        await channel.send("🚫 Conversation too short to generate a music video")
        return

    # Generate lyrics and scene prompts for the music video
    video_completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a creative writer tasked with turning a Valorant match transcript into a narrative for a short music video. Create a set of lyrics and up to six scene prompts, depending on the content of the transcript and quality of story, for a text-to-video model. The lyrics should reference specific moments from the transcript to create a fun, personalized story, but try to keep it short and poppy. The lyrics should be personalized to the transcript, with references as possible, and a narrative to fit. The scene prompts should focus on the visual elements only. Remember that each scene prompt should be written as a standalone scene, and should be able to be read independently. Reply in the format of:\n Lyrics: [lyrics]\n Scene Prompt 1: [scene prompt], etc",
            },
            {"role": "user", "content": transcript},
        ],
    )

    lyrics_and_scenes = video_completion.choices[0].message.content

    # Parse lyrics and scenes
    lyrics = lyrics_and_scenes.split("Lyrics:")[1].split("Scene Prompt")[0].strip()
    scenes = [scene.strip() for scene in lyrics_and_scenes.split("Scene Prompt") if scene.strip() != ""][1:]

    # Send initial message with lyrics and scene prompts
    initial_message = await channel.send(f"Here are the lyrics for the music video:\n\n{lyrics[:1500]}\n\nScene prompts: {scenes}")

    # Create song using Suno API
    song_task_id = create_song_request(lyrics)

    # Wait for song to be generated
    song_url = None
    while True:
        if song_task_id:
            song_info = create_request(f"https://api.goapi.ai/api/suno/v1/music/{song_task_id}", {
                "X-API-Key": SONG_API_TOKEN,
                "Content-Type": "application/json"
            }, method="get")
            if song_info and song_info["data"]["status"] == "completed":
                song_url = song_info["data"]["clips"][list(song_info["data"]["clips"].keys())[0]]["audio_url"]
                break
        await asyncio.sleep(10)

    # Update message with generated song URL
    await initial_message.edit(content=f"Here are the lyrics for the music video:\n\n{lyrics[:1500]}\n\nScene prompts: {scenes}\n\n✅ Song generated: [Song Link]({song_url})")

    # Create videos for each scene
    video_ids = [create_video_request(scene, i + 1) for i, scene in enumerate(scenes[:6])]

    # Wait for all videos to be generated
    video_urls = [None] * len(video_ids)
    while None in video_urls:
        for i, video_id in enumerate(video_ids):
            if video_id and not video_urls[i]:
                video_info = create_request(f"https://api.useapi.net/v1/minimax/videos/{video_id}", {
                    "Authorization": f"Bearer {VIDEO_API_TOKEN}",
                    "Content-Type": "application/json"
                }, method="get")
                if video_info and video_info["status"] == 2:  # Completed
                    video_urls[i] = video_info["videoURL"]
                    # Update the message with each video as it's completed
                    await initial_message.edit(content=f"Here are the lyrics for the music video:\n\n{lyrics[:1500]}\n\nScene prompts: {scenes}\n\n✅ Song generated: [Song Link]({song_url})\n\n" + "\n".join([f"✅ Scene {i + 1} generated: [Video Link]({video_url})" for i, video_url in enumerate(video_urls) if video_url]))
        await asyncio.sleep(10)
    # Merge videos and song
    await merge_videos_and_song(song_url, video_urls)

async def merge_videos_and_song(song_url, video_urls):
    # Step 1: Download song and videos
    async with ClientSession() as session:
        song_path = await download_file(session, song_url, 'song.mp3')
        video_paths = []
        for i, video_url in enumerate(video_urls):
            video_path = await download_file(session, video_url, f'video_{i+1}.mp4')
            video_paths.append(video_path)

    # Step 2: Load videos using MoviePy
    video_clips = [VideoFileClip(video) for video in video_paths]
    
    # Step 3: Concatenate and loop the videos until they match the song duration
    concatenated_clip = concatenate_videoclips(video_clips)

    song_audio = AudioFileClip(song_path)
    song_duration = song_audio.duration
    final_video_clip = loop(concatenated_clip, duration=song_duration)
    final_video_clip = final_video_clip.set_audio(song_audio)

    # Step 4: Write the output to a file
    output_path = 'final_output.mp4'
    final_video_clip.write_videofile(output_path, codec='libx264', audio_codec='aac')

    # Step 5: Clean up temporary files
    song_audio.close()
    final_video_clip.close()
    concatenated_clip.close()
    for video in video_clips:
        video.close()

async def download_file(session, url, filename):
    async with session.get(url) as response:
        if response.status == 200:
            with open(filename, 'wb') as f:
                f.write(await response.read())
            return filename

@bot.command()
async def stop_recording(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()
        del connections[ctx.guild.id]
        await ctx.delete()
    else:
        await ctx.respond("🚫 Not recording here")

bot.run(env.get("DISCORD_BOT_TOKEN"))