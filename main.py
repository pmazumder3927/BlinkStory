import os
import random
import time
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

MAX_SCENES = 5
MAX_CONCURRENT_VIDEOS = 2

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
    keywords=["Reyna", "Nayo", "Sage", "Killjoy", "Jett", "Viper", "Raze", "Skye", "Cypher", "Sova", "Brimstone", "Omen", "Phoenix", "KAY/O", "Chamber", "Neon", "Fade", "Deadlock", "Sage", "Viper", "Raze", "Skye", "Cypher", "Sova", "Brimstone", "Omen", "Phoenix", "KAY/O", "Chamber", "Neon", "Fade", "Deadlock", "Pramit", "Jon", "Lucy", "Lily", "Kwon"]
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

def create_song_request(lyrics, tags):
    headers = {
        "X-API-Key": SONG_API_TOKEN,
        "Content-Type": "application/json"
    }
    print("lyrics")
    print(lyrics)
    body = {
        "custom_mode": True,
        "mv": "chirp-v3-5",
        "input": {
            "prompt": lyrics,
            "title": "discord slander",
            "tags": tags,
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
        await ctx.respond("hop in vc")
        return

    vc = await voice.channel.connect()
    connections.update({ctx.guild.id: vc})

    vc.start_recording(
        discord.sinks.WaveSink(),
        once_done,
        ctx.channel,
    )
    await ctx.respond("whats good")

async def once_done(sink: discord.sinks, channel: discord.TextChannel, *args):
    recorded_users = {user_id: await channel.guild.fetch_member(user_id) for user_id in sink.audio_data.keys()}
    print(recorded_users)
    await sink.vc.disconnect()

    words_list = []

    for user_id, audio in sink.audio_data.items():
        audio_data = audio.file.read()
        payload: FileSource = {
            "buffer": audio_data,
        }
        # save all the audio to files under a folder for the user
        os.makedirs(f"audio/{user_id}", exist_ok=True)
        with open(f"audio/{user_id}/{user_id}_{time.time()}.wav", "wb") as f:
            f.write(audio_data)
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)

        words = response["results"]["channels"][0]["alternatives"][0]["words"]
        words = [word.to_dict() for word in words]

        for word in words:
            # if word["speaker"] != 0:
            #     user_id = word["speaker"]
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
            speaker_name = recorded_users[word["speaker"]].display_name if word["speaker"] in recorded_users else word["speaker"]
            transcript += f"\n\nSpeaker {speaker_name}: "
            current_speaker = word["speaker"]
        transcript += f"{word['punctuated_word']} "

    transcript = transcript.strip()

    # replace transcript names with the names of the people in the call
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

    print(transcript)

    # if transcript is too short, don't generate a music video
    if len(transcript) < 100:
        await channel.send("🚫 Conversation too short to generate a music video")
        return

    # Generate lyrics and scene prompts for the music video
    prompt = r"""You are a creative writer, named BlinkBot, tasked with turning a discord call transcript between friends into a narrative for a short music video. Create a set of lyrics and 6 scene prompts, depending on the content of the transcript and quality of story, for a text-to-video model. 
    1. Tags for the song genre and style
    2. The lyrics, which should reference specific moments from the transcript to create a fun, personalized story, but try to keep it short and poppy. The lyrics should be personalized to the transcript, with references as possible, and a narrative to fit. 
    3. A visual theme paragraph, which should be a semi-long description of the visual theme of the music video. Example: "realistic cinematic cyberpunk style in an fps game, explosions in the background, photorealistic music video", or maybe "asurrealist, animated, dreamlike illustrations in a painted world" along with a synopsis of the theme of the song.

    Reply in the format of (example output):
    Tags: rock grunge pop
    Lyrics: [lyrics]
    Visual Theme: [visual theme sentences]
    """
    video_completion = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4095,
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {"role": "user", "content": transcript},
        ],
    )

    scenes_prompt = r"""
    You are a creative scene writer who takes a transcript and lyrics and creates a series of 6 scene prompts to feed into a generative model to create a music video over the lyrics, which are generated from the story of the transcript. Try to discern the full context of the situation, then create each prompt as a standalone, detailed description of the scene. 
    Be specific, and only describe the visual elements of the scene. Be creative with what each character looks like, and describe them specifically, and give them a name tag in every single scene description, so their name is visually visible. Make sure there is something to visually follow from scene-to-scene which references the lyrics, especially the chorus for impact. Be extremely extra and visually compelling, describing the scene ambiance, weather, explosions, etc.

    Good example prompts

    Scene 1:
    [Setting: A large digital stage, displaying huge LED screens with patterns simulating an epic final showdown. The atmosphere is vibrant with pulsating light effects syncing with the beats.] - *Character Focus: PRAMIT and TEAM* are in the spotlight, posed victoriously with their in-game avatars displayed. The team's outfits are a fusion of sportswear and high-tech armor, glowing with the harmony of colors. - The scene embodies celebration, camaraderie, and triumph, aligning with "In this game, we’re never in doubt." - Visual Element: The camera pulls back to reveal the entire arena alight with moving visuals and fireworks of colors, creating a grand, conclusive panorama, as the outro plays with “Shower's clear, shine bright, no fear.”

    Begin each scene with a complete description of everything on screen, with character descriptions, color, style, and tone
    """

    lyrics_and_scenes = video_completion.choices[0].message.content

    # Parse lyrics and scenes
    tags = lyrics_and_scenes.split("Tags:")[1].split("Lyrics:")[0].strip()
    lyrics = lyrics_and_scenes.split("Lyrics:")[1].split("Scene Prompt")[0].strip()
    # scenes = [scene.strip() for scene in lyrics_and_scenes.split("Scene Prompt") if scene.strip() != ""][1:]
    visual_theme = lyrics_and_scenes.split("Visual Theme:")[1].strip()
    print("Song tags:")
    print(tags)
    print("Visual theme:")
    print(visual_theme)
    scenes_prompt_completion = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4095,
        messages=[
            {
                "role": "system",
                "content": scenes_prompt,
            },
            {"role": "user", "content": transcript + f"\n\nLyrics: {lyrics}"},
        ],
    )
    scenes = scenes_prompt_completion.choices[0].message.content.split("Scene ")[1:]
    # append visual theme to the end of each scene
    scenes = [scene + f"\n\nVisual theme: {visual_theme}" for scene in scenes]
    for i, scene in enumerate(scenes):
        print(f"Scene {i + 1}: {scene}")

    # Send initial message with lyrics and scene prompts
    initial_message = await channel.send(f"im thinking so hard rn")
    # Initialize variables
    video_ids = [None] * MAX_SCENES
    video_urls = [None] * MAX_SCENES
    in_progress_videos = 0
    next_video_index = 0

    # Start the song generation request
    song_task_id = create_song_request(lyrics, tags)
    song_url = None

    # Main loop
    while None in video_urls or song_url is None:
        # Start new video requests if under the concurrency limit
        while in_progress_videos < MAX_CONCURRENT_VIDEOS and next_video_index < MAX_SCENES:
            scene = scenes[next_video_index]
            video_id = create_video_request(scene, next_video_index + 1)
            video_ids[next_video_index] = video_id
            in_progress_videos += 1
            next_video_index += 1

        # Check the status of the song
        if song_task_id and song_url is None:
            song_info = create_request(f"https://api.goapi.ai/api/suno/v1/music/{song_task_id}", {
                "X-API-Key": SONG_API_TOKEN,
                "Content-Type": "application/json"
            }, method="get")
            if song_info and song_info["data"]["status"] == "completed":
                song_url = song_info["data"]["clips"][list(song_info["data"]["clips"].keys())[0]]["audio_url"]

        # Check the status of video requests
        for i in range(len(video_ids)):
            if video_ids[i] and video_urls[i] is None:
                video_info = create_request(f"https://api.useapi.net/v1/minimax/videos/{video_ids[i]}", {
                    "Authorization": f"Bearer {VIDEO_API_TOKEN}",
                    "Content-Type": "application/json"
                }, method="get")
                if video_info:
                    if video_info["status"] == 2:  # Completed
                        video_urls[i] = video_info["downloadURL"]
                        in_progress_videos -= 1
                    elif video_info["status"] == 5:  # Moderated
                        video_urls[i] = ""
                        in_progress_videos -= 1

        # Update the user with the progress
        thinking_text = random.choice(["thinking", "thinking hard", "thinking so hard rn", "this is taking a while", "doin stuff", "lol", "bruh"])
        # song_generated_text = f"✅ Song generated: [Song Link]({song_url})\n\n" if song_url else ""
        song_generated_text = random.choice(['zoom toons', 'weeowoo', 'ooga'])
        # video_generated_text = "\n".join([f"✅ Scene {i + 1} generated: [Video Link]({url})" for i, url in enumerate(video_urls) if url])
        video_generated_text = random.choice(['hooga', 'weeowoo', 'zoom toons'])
        await initial_message.edit(content=f"{thinking_text}\n\n{song_generated_text}{video_generated_text}")
        await asyncio.sleep(30)
    # Merge videos and song
    # purge empty video urls
    video_urls = [url for url in video_urls if url]
    output_path = await merge_videos_and_song(song_url, video_urls)
    # send the video, with a message @ everyone in the transcript
    await initial_message.channel.send(file=discord.File(output_path), content="\n".join([f"<@{user_id}>" for user_id in recorded_users.keys()]))

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
    output_path = f"final_output_{time.time()}.mp4"
    final_video_clip.write_videofile(output_path, codec='libx264', audio_codec='aac')

    # upload to 

    # Step 5: Clean up temporary files
    song_audio.close()
    final_video_clip.close()
    concatenated_clip.close()
    for video in video_clips:
        video.close()
    return output_path

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