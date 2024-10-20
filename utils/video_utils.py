from aiohttp import ClientSession
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.all import loop
import time


async def download_file(session, url, filename):
    async with session.get(url) as response:
        if response.status == 200:
            with open(filename, 'wb') as f:
                f.write(await response.read())
            return filename

async def merge_videos_and_song(song_url, song_lyrics, video_urls):
    async with ClientSession() as session:
        song_path = await download_file(session, song_url, 'song.mp3')
        video_paths = [await download_file(session, video_url, f'video_{i+1}.mp4') for i, video_url in enumerate(video_urls)]

    video_clips = [VideoFileClip(video) for video in video_paths]
    concatenated_clip = concatenate_videoclips(video_clips)

    song_audio = AudioFileClip(song_path)
    final_video_clip = loop(concatenated_clip, duration=song_audio.duration).set_audio(song_audio)

    output_path = f"final_output_{time.time()}.mp4"
    final_video_clip.write_videofile(output_path, codec='libx264', audio_codec='aac')

    song_audio.close()
    final_video_clip.close()
    concatenated_clip.close()
    for video in video_clips:
        video.close()

    return output_path

