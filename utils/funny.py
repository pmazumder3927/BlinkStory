import random


async def update_progress_message(initial_message, remaining_time, custom_messages=None):
    if custom_messages is None:
        thinking_text = random.choice(["thinking", "thinking hard", "thinking so hard rn", "this is taking a while", "doin stuff", "lol", "bruh"])
    else:
        thinking_text = random.choice(custom_messages)
    song_generated_text = random.choice(['zoom toons', 'weeowoo', 'ooga'])
    video_generated_text = random.choice(['hooga', 'weeowoo', 'zoom toons'])

    minutes, seconds = divmod(remaining_time, 60)
    time_left_msg = f"{int(minutes)} min {int(seconds)} sec remaining" if remaining_time != -1 else "calculating..."

    await initial_message.edit(content=f"{thinking_text}\n{song_generated_text}{video_generated_text}\n{time_left_msg} til imma bus")