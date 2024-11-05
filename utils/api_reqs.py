import requests
import json
import os

VIDEO_API_URL = "https://api.useapi.net/v1/minimax/videos/create"
VIDEO_API_TOKEN = os.getenv("VIDEO_API_TOKEN")
VIDEO_API_ACCOUNT = os.getenv("VIDEO_API_ACCOUNT")
SONG_API_URL = "https://api.goapi.ai/api/suno/v1/music"
SONG_API_TOKEN = os.getenv("GHETTO_API_TOKEN")

async def check_song_status(song_task_id, song_url):
    if song_task_id and song_url is None:
        song_info = create_request(f"https://api.goapi.ai/api/suno/v1/music/{song_task_id}", {
            "X-API-Key": SONG_API_TOKEN,
            "Content-Type": "application/json"
        }, method="get")
        if song_info and song_info["data"]["status"] == "completed":
            song_url = song_info["data"]["clips"][list(song_info["data"]["clips"].keys())[0]]["audio_url"]
    return song_url

async def get_video_status(video_id): 
    video_info = create_request(f"https://api.useapi.net/v1/minimax/videos/{video_id}", {
        "Authorization": f"Bearer {VIDEO_API_TOKEN}",
        "Content-Type": "application/json"
    }, method="get")
    if video_info:
        if video_info["status"] == 2:  # Completed
            return video_info["downloadURL"]
    return None

async def check_video_status(video_ids, video_urls, in_progress_videos):
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
    return video_urls, in_progress_videos

def create_request(url, headers, body=None, params=None, method="post"):
    if method == "post":
        if isinstance(body, dict):
            body = json.dumps(body)
        response = requests.post(url, headers=headers, data=body)
    elif method == "get":
        response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error with request to {url}: {response.status_code}, {response.text}")
        return None

async def create_video_request(scene_prompt, scene_number):
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
    return create_request(VIDEO_API_URL, headers, body=body).get("videoId")

async def create_video_request_with_image(context, file_id):
    headers = {
        "Authorization": f"Bearer {VIDEO_API_TOKEN}",
        "Content-Type": "application/json"
    }
    print(context)
    body = {
        "prompt": context,
        "promptOptimization": True,
        "maxJobs": 5,
        "fileID": file_id
    }
    return create_request(VIDEO_API_URL, headers, body=body).get("videoId")

async def post_image(image_url, content_type):
    response_image = requests.get(image_url)
    file_content = response_image.content
    url = f"https://api.useapi.net/v1/minimax/files/?account={VIDEO_API_ACCOUNT}"
    headers = {
        "Authorization": f"Bearer {VIDEO_API_TOKEN}",
        "Content-Type": content_type
    }
    return create_request(url, headers, method="post", body=file_content).get("fileID")

def create_song_request(lyrics, tags):
    headers = {
        "X-API-Key": SONG_API_TOKEN,
        "Content-Type": "application/json"
    }
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
    return create_request(SONG_API_URL, headers, body=body).get("data", {}).get("task_id")