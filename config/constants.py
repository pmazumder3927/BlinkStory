"""
Application constants and configuration values.
"""

# Discord Configuration
DISCORD_CHANNEL_ID = 1298169696356536371

# Video Generation Limits
MAX_SCENES = 12
MAX_CONCURRENT_VIDEOS = 3

# API Endpoints
VIDEO_API_URL = "https://api.useapi.net/v1/minimax/videos/create"
SONG_API_URL = "https://api.goapi.ai/api/suno/v1/music"

# Deepgram Configuration
DEEPGRAM_MODEL = "nova-2"
DEEPGRAM_OPTIONS = {
    "smart_format": True,
    "utterances": True,
    "punctuate": True,
    "diarize": True,
    "detect_language": True
}

# File Paths
COMPRESSED_OUTPUT_PATH = "./compressed_output.mp4"
CLIENT_SECRET_FILE = "client_secret.json"

# Video Processing
VIDEO_COMPRESSION_QUALITY = 50 