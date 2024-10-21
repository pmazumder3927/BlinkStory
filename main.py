import discord
from dotenv import load_dotenv
from os import environ as env
from manager import GenerationManager

class BotManager:
    def __init__(self):
        self.connections = {}
        self.generation_in_progress = False  # Track if generation is in progress bot-wide

    async def once_done(self, sink: discord.sinks, channel: discord.TextChannel, *args):
        await sink.vc.disconnect()
        generation_manager = GenerationManager(channel, sink)
        
        # Start the video generation process
        await generation_manager.generate_video()
        
        # Mark that the generation is complete
        self.generation_in_progress = False

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

bot = discord.Bot()

# Bind the commands to the BotManager instance
@bot.command()
async def record(ctx):
    await bot_manager.record(ctx)

@bot.command()
async def stop_recording(ctx):
    await bot_manager.stop_recording(ctx)

bot.run(env.get("DISCORD_BOT_TOKEN"))