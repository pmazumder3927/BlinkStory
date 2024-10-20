import asyncio
import discord
from utils.api_reqs import check_song_status, check_video_status, create_song_request, create_video_request
from utils.funny import update_progress_message
from utils.plot import PlotManager
from utils.transcript import replace_usernames, transcribe_audio
from utils.video_utils import compress_video, merge_videos_and_song
from deepgram import DeepgramClient, PrerecordedOptions
import os

from utils.youtube import YouTubeUploader
MAX_SCENES = 12
MAX_CONCURRENT_VIDEOS = 4
deepgram = DeepgramClient(os.getenv("DEEPGRAM_API_TOKEN"))
options = PrerecordedOptions(
    model="nova-2",
    smart_format=True,
    utterances=True,
    punctuate=True,
    diarize=True,
    detect_language=True,
    keywords=["Reyna", "Nayo", "Sage", "Killjoy", "Viper", "Raze", "Skye", "Cypher", "Sova", "Brimstone", "Omen", "Phoenix", "KAY/O", "Chamber", "Neon", "Fade", "Deadlock", "Pramit", "Jon", "Lucy", "Lily", "Kwon"]
)

class GenerationManager:
    def __init__(self, channel, sink):
        self.plot_manager = PlotManager()
        self.channel = channel
        self.sink = sink

    async def generate_transcript(self, sink):
        words_list = await transcribe_audio(sink, deepgram, options)
        recorded_users = {user_id: await self.channel.guild.fetch_member(user_id) for user_id in sink.audio_data.keys()}
        transcript = ""
        current_speaker = None
        for word in words_list:
            if "speaker" in word and word["speaker"] != current_speaker:
                speaker_name = recorded_users[word["speaker"]].display_name if word["speaker"] in recorded_users else word["speaker"]
                transcript += f"\n\nSpeaker {speaker_name}: "
                current_speaker = word["speaker"]
            transcript += f"{word['punctuated_word']} "
        return replace_usernames(transcript.strip())

    async def generate_video(self):
        # step 1: extract transcript information from the audio
        transcript = await self.generate_transcript(self.sink)
        print("Transcript:", transcript)

        # step 2: generate lyrics and scenes from the transcript
        tags, lyrics, visual_theme, scenes = await self.plot_manager.generate_lyrics_and_scenes(transcript, MAX_SCENES)
        print("Tags:", tags)
        print("Lyrics:", lyrics)
        print("Visual Theme:", visual_theme)
        for i, scene in enumerate(scenes):
            print(f"Scene {i+1}: {scene}")

        # step 3: generate a song and videos from the lyrics and scenes
        song_task_id = create_song_request(lyrics, tags)
        video_urls, song_url = await self.handle_video_generation(scenes, song_task_id)
        subtitle_properties = await self.plot_manager.generate_subtitles(lyrics)

        # step 4: merge videos and send final output
        output_path = await merge_videos_and_song(song_url, lyrics, video_urls, subtitle_properties)
        # create compressed version to send
        compressed_path = "./compressed_output.mp4"
        compress_video(output_path, compressed_path, 50)
        await self.channel.send(file=discord.File(compressed_path))

        # upload full resolution version to youtube
        youtube_data = await self.plot_manager.generate_youtube_data()
        youtube_uploader = YouTubeUploader(client_secret_file="client_secret.json")
        link = youtube_uploader.upload_video(output_path, youtube_data=youtube_data)
        await self.channel.send(link)

    async def handle_video_generation(self, scenes, song_task_id):
        initial_message = await self.channel.send("im thinking so hard rn")
        video_ids = [None] * MAX_SCENES
        video_urls = [None] * MAX_SCENES
        in_progress_videos = 0
        next_video_index = 0
        song_url = None

        while None in video_urls or song_url is None:
            # Start new video requests
            while in_progress_videos < MAX_CONCURRENT_VIDEOS and next_video_index < MAX_SCENES:
                scene = scenes[next_video_index]
                video_id = create_video_request(scene, next_video_index + 1)
                video_ids[next_video_index] = video_id
                in_progress_videos += 1
                next_video_index += 1

            # Check the status of the song
            song_url = await check_song_status(song_task_id, song_url)

            # Check the status of video requests
            video_urls, in_progress_videos = await check_video_status(video_ids, video_urls, in_progress_videos)

            await update_progress_message(initial_message, song_url, video_urls, custom_messages=await self.plot_manager.generate_progress_messages(''.join(scenes)))
            await asyncio.sleep(30)

        return video_urls, song_url