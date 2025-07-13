import asyncio
import io
import re
import discord
from dotenv import load_dotenv
from os import environ as env

import requests
from src.manager import GenerationManager
from src.utils.api_reqs import create_video_request_with_image, get_video_status, post_image
from src.utils.plot import generate_image_prompt, generate_message_reply
from src.utils.synthesis import synthesize_and_stream_audio
from src.utils.sinks import RealTimeTranscriptionSink
from config.constants import DISCORD_CHANNEL_ID

CHANNEL_ID = DISCORD_CHANNEL_ID

class BotManager:
    def __init__(self):
        self.connections = {}
        self.generation_in_progress = False  # Track if generation is in progress bot-wide
        self.image_queue = []

    async def once_done(self, sink: discord.sinks, channel: discord.TextChannel, *args):
        await sink.vc.disconnect()
        generation_manager = GenerationManager(channel, sink)
        
        # Start the video generation process
        await generation_manager.generate_video()
        
        # Mark that the generation is complete
        self.generation_in_progress = False
    
    async def imitate(self, ctx):
        # if already in a vc, don't connect again
        if ctx.guild.id in self.connections:
            self.connections[ctx.guild.id].stop_recording()
            return
        voice = ctx.author.voice
        if not voice:
            await ctx.respond("hop in vc")
            return

        vc = await voice.channel.connect()
        self.connections.update({ctx.guild.id: vc})
        async def when_done(sink: discord.sinks, channel: discord.TextChannel, *args):
            await vc.disconnect()
        sink = RealTimeTranscriptionSink(transcription_method='deepgram')
        vc.start_recording(sink, when_done, ctx)

    async def add_image_to_queue(self, original_message, prompt_message):
        if len(self.image_queue) > 2:
            await prompt_message.channel.send("im busy loser")
            return
        # get the last 10 messages as context
        # messages = await message.channel.history(limit=10).flatten()
        # context = "\n".join([f"{m.author.display_name}: {m.content}" for m in messages[::-1]])
        # image_prompt = await generate_image_prompt(context)
        progress_message = await prompt_message.channel.send("ok")
        image_prompt = prompt_message.content
        image_prompt = re.sub(r'<@.*?>', '', image_prompt)
        file_id = (await post_image(original_message.attachments[0].url, original_message.attachments[0].content_type))
        video_id = await create_video_request_with_image(image_prompt, file_id)
        await progress_message.delete()
        self.image_queue.append(prompt_message)
        asyncio.create_task(self.check_video_status(video_id, prompt_message))
    
    async def check_video_status(self, video_id, message):  
        while True:
            video_url = await get_video_status(video_id)
            if video_url:
                # download the video
                video_response = requests.get(video_url)
                video_content = io.BytesIO(video_response.content)
                video_content.seek(0)
                video_file = discord.File(video_content, filename=f"{video_id}.mp4")
                await message.channel.send(file=video_file, reference=message)
                self.image_queue.remove(message)
                break
            await asyncio.sleep(10)

    async def record(self, ctx):
        # if generation is in progress, don't start another one
        if self.generation_in_progress:
            await ctx.respond("already working on a generation")
            return

        voice = ctx.author.voice

        if not voice:
            await ctx.respond("hop in vc")
            return

        vc = await voice.channel.connect()
        self.connections.update({ctx.guild.id: vc})
        
        # Set generation in progress bot-wide
        self.generation_in_progress = True
        
        await self.record_audio(vc, ctx)

    async def record_audio(self, vc, ctx):
        vc.start_recording(
            discord.sinks.WaveSink(),
            self.once_done,
            ctx.channel,
        )
        await ctx.respond("whats good")

    async def stop_recording(self, ctx):
        if ctx.guild.id in self.connections:
            await ctx.respond("stopping recording")
            vc = self.connections[ctx.guild.id]
            vc.stop_recording()
            del self.connections[ctx.guild.id]
            # Reset the generation in progress flag bot-wide
            self.generation_in_progress = False
        else:
            await ctx.respond("ur high bruh")


# Initialize BotManager
bot_manager = BotManager()

bot = discord.Bot(intents=discord.Intents.all())

# Bind the commands to the BotManager instance
@bot.command()
async def record(ctx):
    await bot_manager.record(ctx)

@bot.command()
async def stop_recording(ctx):
    await bot_manager.stop_recording(ctx)

@bot.command()
async def imitate(ctx):
    await bot_manager.imitate(ctx)

@bot.event
async def on_message(message):
    if message.channel.id == CHANNEL_ID and not message.author.bot:
        # Create a placeholder message that mirrors the original message
        # get the last messages for the day as context in the channel
        messages = await message.channel.history(limit=100).flatten()
        # output them as a string and reverse order
        messages_string = "\n".join([f"{m.author.display_name}: {m.content}" for m in messages[::-1]])
        print(messages_string)
        mirrored_message = await generate_message_reply(messages_string)
        if mirrored_message != "":
            await message.channel.send(mirrored_message)

    # if mentioned
    if bot.user.mentioned_in(message):
        # if the message mentioned by the message has an image, add image to the queue
        if message.reference and message.reference.resolved:
            if message.reference.resolved.attachments:
                if message.reference.resolved.attachments[0].filename.endswith(('.png', '.jpg', '.jpeg')):
                    await bot_manager.add_image_to_queue(message.reference.resolved, message)

def main():
    """Main entry point for the Discord bot."""
    load_dotenv()
    bot.run(env.get("DISCORD_BOT_TOKEN"))

if __name__ == "__main__":
    main()