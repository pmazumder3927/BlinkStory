import math
import os
import re
import subprocess
from aiohttp import ClientSession
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.all import loop
import stable_whisper
import time


async def download_file(session, url, filename):
    async with session.get(url) as response:
        if response.status == 200:
            with open(filename, 'wb') as f:
                f.write(await response.read())
            return filename

async def merge_videos_and_song(song_url, song_lyrics, video_urls, subtitle_properties):
    model = stable_whisper.load_model("base")
    lyrics = re.sub(r'\[.*?\]|\(.*?\)', '', song_lyrics)
    # remove all symbols and punctuation other than periods, commas, and question marks
    lyrics = re.sub(r'[^\w\s.,?!]', '', lyrics).strip()
    # delete existing ass file
    ass_path = './output.ass'
    if os.path.exists(ass_path):
        os.remove(ass_path)
    print("subtitle_properties")
    print(subtitle_properties)

    async with ClientSession() as session:
        song_path = await download_file(session, song_url, 'song.mp3')
        video_paths = [await download_file(session, video_url, f'video_{i+1}.mp4') for i, video_url in enumerate(video_urls)]

    result = model.align('./song.mp3', lyrics, language='en', fast_mode=True, regroup='cm_sp=,* /，/\n/\\_sg=.5_sp=.* /。/?/？')
    highlight_color = subtitle_properties["font_color"].strip("#")
    ass_out = result.to_ass(ass_path, karaoke=True, font=subtitle_properties["font"], highlight_color=highlight_color)

    video_clips = [VideoFileClip(video) for video in video_paths]
    concatenated_clip = concatenate_videoclips(video_clips)

    song_audio = AudioFileClip(song_path)
    final_video_clip = loop(concatenated_clip, duration=song_audio.duration).set_audio(song_audio)

    output_path = f"final_output_with_subtitles_{time.time()}.mp4"
    final_video_clip.write_videofile(output_path, codec='libx265', audio_codec='aac', ffmpeg_params=['-vf', f"subtitles={ass_path}"])

    song_audio.close()
    final_video_clip.close()
    concatenated_clip.close()
    for video in video_clips:
        video.close()

    return output_path

# Calculate target bitrate based on desired file size (in bits)
def calculate_target_bitrate(target_size_mb, duration_s):
    target_size_bits = target_size_mb * 8 * 1024 * 1024
    target_bitrate = target_size_bits / duration_s
    return target_bitrate

# Get the duration of the video using ffprobe
def get_video_duration(input_path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", input_path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return float(result.stdout)

# Compress video to target size
def compress_video(input_path, output_path, target_size_mb):
    duration = get_video_duration(input_path)
    target_bitrate = calculate_target_bitrate(target_size_mb, duration)
    target_bitrate_k = math.floor(target_bitrate / 1000)  # in kilobits per second

    for attempt in range(10):
        print(f"Attempt {attempt + 1}: Compressing with target bitrate {target_bitrate_k}k...")
        
        command = [
            "ffmpeg", "-i", input_path, "-b:v", f"{target_bitrate_k}k", "-bufsize", f"{target_bitrate_k}k",
            "-maxrate", f"{target_bitrate_k}k", "-pass", "1", "-c:a", "aac", "-b:a", "128k", output_path, "-y"
        ]
        subprocess.run(command)

        # Check if the file size is under the target size
        output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        if output_size_mb <= target_size_mb:
            print(f"Compression successful: Output file size is {output_size_mb:.2f} MB")
            break
        else:
            print(f"Output file size is {output_size_mb:.2f} MB, reducing bitrate further...")
            target_bitrate_k = int(target_bitrate_k * 0.85)  # Reduce bitrate further if needed
    else:
        print("Warning: Maximum attempts reached. Could not reach target size.")