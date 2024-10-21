import discord
from dotenv import load_dotenv
from os import environ as env
from manager import GenerationManager

bot = discord.Bot()
connections = {}

async def once_done(sink: discord.sinks, channel: discord.TextChannel, *args):
    await sink.vc.disconnect()
    generation_manager = GenerationManager(channel, sink)
    await generation_manager.generate_video()

@bot.command()
async def record(ctx):
    voice = ctx.author.voice

    if not voice:
        await ctx.respond("hop in vc")
        return

    vc = await voice.channel.connect()
    connections.update({ctx.guild.id: vc})
    await record_audio(vc, ctx)

async def record_audio(vc, ctx):
    vc.start_recording(
        discord.sinks.WaveSink(),
        once_done,
        ctx.channel,
    )
    await ctx.respond("whats good")

@bot.command()
async def stop_recording(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()
        del connections[ctx.guild.id]
        await ctx.delete()
        await ctx.respond("🚫 Not recording here")

bot.run(env.get("DISCORD_BOT_TOKEN"))