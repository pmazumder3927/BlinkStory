import random


async def update_progress_message(initial_message, song_url, video_urls):
    thinking_text = random.choice(["thinking", "thinking hard", "thinking so hard rn", "this is taking a while", "doin stuff", "lol", "bruh"])
    song_generated_text = random.choice(['zoom toons', 'weeowoo', 'ooga'])
    video_generated_text = random.choice(['hooga', 'weeowoo', 'zoom toons'])
    await initial_message.edit(content=f"{thinking_text}\n\n{song_generated_text}{video_generated_text}")