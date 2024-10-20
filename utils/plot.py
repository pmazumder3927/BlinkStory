import openai
import os

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

class PlotManager:
    def __init__(self):
        self.client = client

    def parse_lyrics_and_scenes(self, lyrics_and_scenes):
        tags = lyrics_and_scenes.split("Tags:")[1].split("Lyrics:")[0].strip()
        lyrics = lyrics_and_scenes.split("Lyrics:")[1].split("Scene Prompt")[0].strip()
        visual_theme = lyrics_and_scenes.split("Visual Theme:")[1].strip()
        return tags, lyrics, visual_theme

    async def generate_lyrics_and_scenes(self, transcript):
        prompt = r"""You are a creative writer, named BlinkBot, tasked with turning a discord call transcript between friends into a narrative for a short music video. Create a set of lyrics and 6 scene prompts, depending on the content of the transcript and quality of story, for a text-to-video model. 
        1. Tags for the song genre and style
        2. The lyrics, which should reference specific moments from the transcript to create a fun, personalized story, but try to keep it short and poppy. The lyrics should be personalized to the transcript, with references as possible, and a narrative to fit. You can use italics to create sound effects in the song.
        3. A visual theme paragraph, which should be a semi-long description of the visual theme of the music video. Example: "realistic cinematic cyberpunk style in an fps game, explosions in the background, photorealistic music video", or maybe "asurrealist, animated, dreamlike illustrations in a painted world" along with a synopsis of the theme of the song.

        Reply in the format of (example output):
        Tags: rock grunge pop
        Lyrics: [lyrics]
        Visual Theme: [visual theme sentences]
        """
        video_completion = self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=4095,
            messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        )
        tags, lyrics, visual_theme = self.parse_lyrics_and_scenes(video_completion.choices[0].message.content)
        scenes = await self.generate_scenes(transcript, lyrics, visual_theme)
        return tags, lyrics, visual_theme, scenes

    async def generate_scenes(self, transcript, lyrics, visual_theme):
        scenes_prompt = r"""
        You are a creative scene writer who takes a transcript and lyrics and creates a series of 6 scene prompts to feed into a generative model to create a music video over the lyrics, which are generated from the story of the transcript. Try to discern the full context of the situation, then create each prompt as a standalone, detailed description of the scene. 
        Be specific, and only describe the visual elements of the scene. Be creative with what each character looks like, and describe them specifically, and give them a name tag in every single scene description, so their name is visually visible. Make sure there is something to visually follow from scene-to-scene which references the lyrics, especially the chorus for impact. Be extremely extra and visually compelling, describing the scene ambiance, weather, explosions, etc.

        Good example prompts

        Scene 1:
        [Setting: A large digital stage, displaying huge LED screens with patterns simulating an epic final showdown. The atmosphere is vibrant with pulsating light effects syncing with the beats.] - *Character Focus: PRAMIT and TEAM* are in the spotlight, posed victoriously with their in-game avatars displayed. The team's outfits are a fusion of sportswear and high-tech armor, glowing with the harmony of colors. - The scene embodies celebration, camaraderie, and triumph, aligning with "In this game, we’re never in doubt." - Visual Element: The camera pulls back to reveal the entire arena alight with moving visuals and fireworks of colors, creating a grand, conclusive panorama, as the outro plays with “Shower's clear, shine bright, no fear.”

        Begin each scene with a complete description of everything on screen, with character descriptions, color, style, and tone
        """
        scenes_prompt_completion = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=4095,
            messages=[
                {"role": "system", "content": scenes_prompt},
                {"role": "user", "content": f"{transcript}\n\nLyrics: {lyrics}"},
            ],
            )
        scenes = scenes_prompt_completion.choices[0].message.content.split("Scene ")[1:]
        return [scene + f"\n\nVisual theme: {visual_theme}" for scene in scenes]