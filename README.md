# BlinkStory 🎵🎬

## An AI-powered Discord bot that transforms voice conversations into original music videos with generated lyrics, scenes, and subtitles.

Listen to you and your friends and uses a combination of generative models to create subtitled music videos with original content based off the discord conversation content. The whole pipeline is automated by model pipelines, including the song theme, lyrics, scenes, and even subtitle fonts and colors!

## ✨ What It Does

- **Records Discord voice conversations** and transcribes them using AI
- **Generates original song lyrics** based on the conversation content
- **Creates video scenes** that match the conversation themes
- **Synthesizes custom music** using Suno AI
- **Produces complete music videos** with subtitles and visual effects
- **Uploads to YouTube** automatically
- **Creates videos from images** with custom prompts

## 🚀 Quick Demo

1. Join a Discord voice channel
2. Use `/record` to start recording
3. Have a conversation with friends
4. Use `/stop_recording` to generate your music video
5. Watch as AI creates a complete video from your chat!

## 🛠️ Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your API tokens
   ```

3. **Run the bot**
   ```bash
   python src/main.py
   ```

## 📁 Project Structure

```
BlinkStory/
├── src/                    # Main application
│   ├── main.py            # Discord bot
│   ├── manager.py         # Video generation
│   └── utils/             # Core utilities
├── config/                # Configuration
├── examples/              # Development notebooks
├── requirements.txt       # Dependencies
└── README.md             # This file
```

## 🎮 Commands

- `/record` - Start recording voice channel
- `/stop_recording` - Stop and generate video
- `/imitate` - Real-time transcription mode

## 🔧 Required APIs

- Discord Bot Token
- Deepgram (speech-to-text)
- UseAPI (video generation)
- GoAPI/Suno (music generation)
- YouTube API (upload)

## 🤖 How It Works

1. **Recording** → Bot joins voice channel and records audio
2. **Transcription** → AI converts speech to text with speaker identification
3. **Analysis** → Conversation is analyzed for themes and context
4. **Generation** → AI creates lyrics, scenes, and music simultaneously
5. **Assembly** → Videos are merged with music and subtitles
6. **Delivery** → Final video sent to Discord and uploaded to YouTube

## 📝 License

MIT License - feel free to use and modify
