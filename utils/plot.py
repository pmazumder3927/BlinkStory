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
        return tags, lyrics

    async def generate_lyrics_and_scenes(self, transcript, num_scenes):
        prompt = r"""
        Turn a Discord call transcript between friends into a song by creating a set of lyrics that highlights specific moments in the conversation and fits within the context of a music video. 

        The lyrics should establish a strong narrative, personalized and engagingly referencing the conversation. Make as many clever references as you can. You may incorporate multiple singers to enhance the storytelling and ensure the lyrics last around 3 minutes.

        # Steps

        1. Review the transcript to identify key moments, themes, and interactions between the friends. Especially note humorous and/or memorable moments or banter
        2. Determine the overall mood and style of the music video based on the conversation
        3. Decide on the song's genre and style tags that best match the identified theme. Keep these as descriptive music genres and vibes
        4. Create a lyrics structure that weaves in the identified moments, references specific people, and matches the selected music style, along with using vernacular that fits the vibe of the conversations
        5. Assign parts of the lyrics to different singers if multiple voices will enhance the narrative, specifying their voice tones where applicable.
        6. Use italics for sound effects or non-verbal moments if they contribute to the song.

        # Output Format

        Reply with:
        - **Tags:** A list of genre or style tags that best describe the music's theme, such as pop, classical, baroque, opera, etc.
        - **Lyrics:** The complete set of lyrics, integrated with specific references to the transcript.
        - Use square brackets to denote different singers and describe their voice tone.
        - Italicize any sound effects or non-verbal components.

        # Examples

        Tags: rock indie acoustic romantic
        Lyrics: 
        [Verse: Female singer with a soft, warm tone]
        There's a moment, when you laughed, *like the morning sunshine*
        [Chorus: Deep male voice, calm and soothing]
        Your stories, they paint, *colors in my mind*

        (Real examples would be extended and more detailed with references derived from the transcript.)
        """
        video_completion = self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=4095,
            messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        )
        tags, lyrics = self.parse_lyrics_and_scenes(video_completion.choices[0].message.content)
        scenes = await self.generate_scenes(transcript, lyrics, num_scenes)
        self.tags = tags
        self.lyrics = lyrics
        self.scenes = scenes
        return tags, lyrics, scenes

    async def generate_scenes(self, transcript, lyrics, num_scenes):
        scenes_prompt = rf"""
        Create a series of {num_scenes} detailed scene prompts for a music video, using a transcript and lyrics as a basis. Each prompt should stand alone, vividly describing only the visual elements of the scene. The scenes should creatively reflect the story conveyed in the transcript and use elements from the lyrics, especially the chorus, to guide the visual narrative. 

        Ensure consistency by re-describing key visual features, such as character appearances, in every scene they appear. Use creative storytelling to captivate the viewer and maintain continuity across the video, including the ambiance, weather effects, and significant visuals like explosions.

        - Each scene description should include:
            - **Setting:** A detailed account of the scene's environment and ambiance, including lighting, background, and weather effects.
            - **Character Descriptions:** Specify the appearance of each character involved, including unique traits or costumes, with their identity clearly marked (e.g., *Character Tag: NAME*).
            - **Visual Elements:** Continuity items that connect scenes, with striking visuals corresponding to lyrics.
            - **Mood and Tone:** The general ambience that matches the music and lyrics.

        # Steps

        1. **Understand the Narrative:** Read the transcript to grasp the underlying story and themes. Identify key emotional beats in the lyrics that can be visually highlighted.
        2. **Develop Scene Prompts:** For each of the {num_scenes}, translate themes and emotions from the lyrics into visual language.
        3. **Identify Visual Continuity:** Choose an element that will appear in multiple scenes as a visual thread that the audience can follow.
        4. **Reiterate Key Descriptions:** Ensure that every reappearance of visual details, especially characters, includes a full description. The scene descriptions should be getting longer and more interesting/intricate as the song progresses, so higher scene numbers should have more detailed descriptions.

        # Output Format

        Each scene prompt must start with a complete description, including setting, character appearances, visual elements, and mood.

        # Examples

        **Scene 1:**
        [Setting: A neon-lit cityscape at night, bustling with energy and life. The scene is alive with shimmering reflections on wet pavements. Rain drizzles softly, creating a mystical glow from the street lamps.] - *Character Focus: SAMANTHA the Sloth* stands under a large umbrella, her fur shimmering with the colors of the city lights. Her attire is a casual-yet-stylish cape, cozy and vibrant. - As the lyrics echo, "Underneath the same sky, we find our way," the camera pans to show moving traffic lights forming a syncopated pattern.

        # Notes

        - Use vivid and imaginative language to make each scene visually dynamic and engaging.
        - Ensure that each character's description is repeated fully for consistency, regardless of the scene number.
        - Balance creativity with narrative coherence, ensuring the story visually flows with the music.
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
                "text": "Automatically generate a YouTube video title, description, and tags based on provided song lyrics and scene descriptions.\n\nUse the given lyrics and scene descriptions to create engaging and relevant content reflecting the theme, mood, and key elements of the input. Ensure the title is compelling, the description is informative, and the tags are relevant to the content.\n\n# Steps\n\n1. **Title Generation**:\n   - Identify key themes, motifs, or unique elements within the input such as \"Neon lights\", \"Digital battlefield\", or character highlights like \"KWON with AWP\".\n   - Craft a concise yet intriguing title that captures the essence of the video content and piques interest. Keep in mind that all of the content generated is from the Discord server \"Blink\" so something along the lines of \"[Tales from Blink/Blink Slander/Blink Adventures / etc]: [Character] is on a roll\" is very funny\n\n2. **Description Creation**:\n   - Summarize the main narrative or themes conveyed through the lyrics and scene description.\n   - Include elements such as character highlights, digital landscapes, and key action points from the lyrics.\n   - Engage the audience by hinting at the excitement and visual spectacle of the video.\n\n3. **Tag Selection**:\n   - Extract relevant tags from prominent elements like character names, technology or gaming terms, and thematic concepts.\n   - Use a mix of broader terms and video-specific keywords to enhance discoverability.\n\n# Output Format\n\n- **Title**: A single line, ideally 50-60 characters.\n- **Description**: A short paragraph, approximately 100-200 words.\n- **Tags**: A list of 5-10 relevant keywords/phrases, separated by commas.\n\n# Example\n\n**Title**: \"Neon Nights in Digital Battlefield - KWON's Tale\"\n\n**Description**: \nJoin KWON in a thrilling adventure across a luminous digital battlefield where technology and nature collide. Experience the synergy of city lights and tactical prowess, as KWON wields the brilliant green energy of his futuristic AWP sniper rifle. With allies like Reyna and Phoenix at his side, and battles set against the backdrop of vibrant landscapes, this video captures the thrill of gaming skill and team coordination in stunning visual style. Don't miss the dynamic action and strategic gameplay as KWON and his friends take on new challenges and shine against all odds.\n\n**Tags**: KWON, AWP sniper, digital battlefield, gaming skill, teamwork, cyber landscape, Pramit, synergy, city lights, tactical gameplay\n\n# Notes\n\n- Ensure the title is SEO-friendly and likely to attract viewers.\n- The description should seamlessly integrate with YouTube's formatting constraints and viewer expectations.\n- Consider the balance between specificity and broad appeal when selecting tags. The title and descriptions should sound badass, and cool, with a vibe that caters to those in their early 20s"
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
                "text": "Analyze the song's lyrics and scene descriptions to determine the most suitable creative choice for the subtitle font and highlight color. Ensure the font is commonly available on Windows systems.\n\n- Evaluate the emotional tone and themes of the song lyrics.\n- Assess the mood and visual style described in the scene.\n- Choose a font that aligns with the overall tone and is a standard Windows font.\n- Select a highlight color that complements the theme and aesthetics.\n\n# Steps\n\n1. **Lyric Analysis**: Examine the lyrics to understand the core emotions, themes, and atmosphere.\n2. **Scene Description Evaluation**: Evaluate the scene descriptions to grasp the visual style and mood.\n3. **Font Selection**: Choose a font that is available on Windows and matches the identified mood and theme.\n4. **Highlight Color Selection**: Select a color that fits both the lyrical themes and the scene's visual style.\n\n# Output Format\n\n- **Font**: Provide the name of the selected font.\n- **Highlight Color**: Provide the hexadecimal code for the chosen color.\n\nExample Format:\n```\n\"font\": \"[Font Name]\",\n\"highlight_color\": \"[Hex Code]\"\n```\n\n# Examples\n\n**Example Input**\n- Lyrics: [Lyrics]\n- Scene Description: [Description of the scene]\n\n**Example Output**\n- Font: \"Arial\"\n- Highlight Color: \"#00FF00\"\n\n(Use real lyrics and scene descriptions for practical application. Ensure the chosen font and color genuinely reflect the inputs, and try to use some lesser known fonts if possible. The colors chosen should be bright enough to work, given that the text color will be white",
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
    
    async def generate_progress_messages(self, lyrics):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Generate a series of progress messages for a music video, based on the lyrics and scene descriptions. Make each message a short sentence, which only vaguely/indirectly hints at the content of the video. Format your answer by putting one message per line. Use slang/casual style, as a discord user, and all lowercase."},
                {"role": "user", "content": f"Lyrics: {lyrics}\nScenes: {self.scenes}"},
            ],
        )
        return response.choices[0].message.content.split("\n")
