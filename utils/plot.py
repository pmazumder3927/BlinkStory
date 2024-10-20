import json
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
        lyrics = lyrics_and_scenes.split("Lyrics:")[1].split("Visual Theme:")[0].strip()
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
        self.tags = tags
        self.visual_theme = visual_theme
        self.lyrics = lyrics
        self.scenes = scenes
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
        return scenes
    
    async def generate_youtube_data(self):
        response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": "Automatically generate a YouTube video title, description, and tags based on provided song lyrics and scene descriptions.\n\nUse the given lyrics and scene descriptions to create engaging and relevant content reflecting the theme, mood, and key elements of the input. Ensure the title is compelling, the description is informative, and the tags are relevant to the content.\n\n# Steps\n\n1. **Title Generation**:\n   - Identify key themes, motifs, or unique elements within the input such as \"Neon lights\", \"Digital battlefield\", or character highlights like \"KWON with AWP\".\n   - Craft a concise yet intriguing title that captures the essence of the video content and piques interest. Keep in mind that all of the content generated is from the Discord server \"Blink\" so something along the lines of \"[Tales from Blink/Blink Slander/Blink Adventures / etc]: [Character] is on a roll\" is very funny\n\n2. **Description Creation**:\n   - Summarize the main narrative or themes conveyed through the lyrics and scene description.\n   - Include elements such as character highlights, digital landscapes, and key action points from the lyrics.\n   - Engage the audience by hinting at the excitement and visual spectacle of the video.\n\n3. **Tag Selection**:\n   - Extract relevant tags from prominent elements like character names, technology or gaming terms, and thematic concepts.\n   - Use a mix of broader terms and video-specific keywords to enhance discoverability.\n\n# Output Format\n\n- **Title**: A single line, ideally 50-60 characters.\n- **Description**: A short paragraph, approximately 100-200 words.\n- **Tags**: A list of 5-10 relevant keywords/phrases, separated by commas.\n\n# Example\n\n**Title**: \"Neon Nights in Digital Battlefield - KWON's Tale\"\n\n**Description**: \nJoin KWON in a thrilling adventure across a luminous digital battlefield where technology and nature collide. Experience the synergy of city lights and tactical prowess, as KWON wields the brilliant green energy of his futuristic AWP sniper rifle. With allies like Reyna and Phoenix at his side, and battles set against the backdrop of vibrant landscapes, this video captures the thrill of gaming skill and team coordination in stunning visual style. Don't miss the dynamic action and strategic gameplay as KWON and his friends take on new challenges and shine against all odds.\n\n**Tags**: KWON, AWP sniper, digital battlefield, gaming skill, teamwork, cyber landscape, Pramit, synergy, city lights, tactical gameplay\n\n# Notes\n\n- Ensure the title is SEO-friendly and likely to attract viewers.\n- The description should seamlessly integrate with YouTube's formatting constraints and viewer expectations.\n- Consider the balance between specificity and broad appeal when selecting tags."
                }
            ]
            },
            {"role": "user", "content": f"Tags: {self.tags}\nLyrics: {self.lyrics}\nVisual Theme: {self.visual_theme}\nScenes: {self.scenes}"}
        ],
        temperature=1,
        max_tokens=2048,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "youtube_video_metadata",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the YouTube video."
                    },
                    "description": {
                        "type": "string",
                        "description": "A detailed description of the YouTube video."
                    },
                    "tags": {
                        "type": "array",
                        "description": "A list of tags relevant to the video for better discoverability.",
                        "items": {
                        "type": "string"
                        }
                    },
                    "categoryId": {
                        "type": "string",
                        "description": "The category ID of the video, e.g., '22' for 'People & Blogs'."
                    }
                    },
                    "required": [
                    "title",
                    "description",
                    "tags",
                    "categoryId"
                    ],
                    "additionalProperties": False
                    }
                }
            }
        )
        return json.loads(response.choices[0].message.content)

    async def generate_subtitles(self, lyrics):
        response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
            "role": "system",
            "content": [
                {
                "text": "Analyze the song's lyrics and scene descriptions to determine the most suitable creative choice for the subtitle font and highlight color. Ensure the font is commonly available on Windows systems.\n\n- Evaluate the emotional tone and themes of the song lyrics.\n- Assess the mood and visual style described in the scene.\n- Choose a font that aligns with the overall tone and is a standard Windows font.\n- Select a highlight color that complements the theme and aesthetics.\n\n# Steps\n\n1. **Lyric Analysis**: Examine the lyrics to understand the core emotions, themes, and atmosphere.\n2. **Scene Description Evaluation**: Evaluate the scene descriptions to grasp the visual style and mood.\n3. **Font Selection**: Choose a font that is available on Windows and matches the identified mood and theme.\n4. **Highlight Color Selection**: Select a color that fits both the lyrical themes and the scene's visual style.\n\n# Output Format\n\n- **Font**: Provide the name of the selected font.\n- **Highlight Color**: Provide the hexadecimal code for the chosen color.\n\nExample Format:\n```\n\"font\": \"[Font Name]\",\n\"highlight_color\": \"[Hex Code]\"\n```\n\n# Examples\n\n**Example Input**\n- Lyrics: [Lyrics]\n- Scene Description: [Description of the scene]\n\n**Example Output**\n- Font: \"Arial\"\n- Highlight Color: \"#00FF00\"\n\n(Use real lyrics and scene descriptions for practical application. Ensure the chosen font and color genuinely reflect the inputs.)",
                "type": "text"
                }
            ]
            },
            {
            "role": "user",
            "content": lyrics
            },
        ],
        temperature=1,
        max_tokens=2048,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
            "name": "font_schema",
            "schema": {
                "type": "object",
                "required": [
                "font",
                "font_color"
                ],
                "properties": {
                "font": {
                    "type": "string",
                    "description": "The name of the font to be used."
                },
                "font_color": {
                    "type": "string",
                    "description": "The color of the font, typically using a hex code."
                }
                },
                "additionalProperties": False
            },
            "strict": True
            }
        }
        )
        return json.loads(response.choices[0].message.content)
