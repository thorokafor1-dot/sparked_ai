import os

from dotenv import load_dotenv

load_dotenv()

import discord
from anthropic import AsyncAnthropic
from discord import app_commands

import session
import voice
from persona import DIFFICULTIES, FEEDBACK_SYSTEM_PROMPT, build_system_prompt

CLAUDE_MODEL = "claude-sonnet-5"

anthropic_client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

TEST_GUILD_ID = int(os.environ["DISCORD_GUILD_ID"]) if os.environ.get("DISCORD_GUILD_ID") else None

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    if TEST_GUILD_ID:
        guild = discord.Object(id=TEST_GUILD_ID)
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    else:
        await tree.sync()
    print(f"Logged in as {client.user}", flush=True)


@tree.command(name="practise", description="Start a cold approach practice session in this channel")
@app_commands.describe(
    difficulty="How guarded she starts (default: neutral)",
    location="Where the scene takes place (default: random)",
)
@app_commands.choices(
    difficulty=[app_commands.Choice(name=d, value=d) for d in DIFFICULTIES]
)
async def practise(
    interaction: discord.Interaction,
    difficulty: app_commands.Choice[str] = None,
    location: str = None,
):
    channel_id = interaction.channel_id
    if session.get_session(channel_id):
        await interaction.response.send_message(
            "A session is already running in this channel. Run /end first.", ephemeral=True
        )
        return

    difficulty_value = difficulty.value if difficulty else "neutral"
    system_prompt = build_system_prompt(difficulty_value, location)
    session.start_session(channel_id, system_prompt)

    await interaction.response.send_message(
        f"Session started ({difficulty_value}). She has no idea you're about to walk up. Just start talking in this channel."
    )


@tree.command(name="end", description="End the current practice session and get feedback")
async def end(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    active = session.end_session(channel_id)
    if not active or not active.messages:
        await interaction.response.send_message(
            "No active session with any messages in this channel.", ephemeral=True
        )
        return

    await interaction.response.defer()

    transcript_lines = []
    for m in active.messages:
        speaker = "Him" if m["role"] == "user" else "Her"
        transcript_lines.append(f"{speaker}: {m['content']}")
    transcript = "\n".join(transcript_lines)

    response = await anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        system=FEEDBACK_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript}],
    )
    feedback = response.content[0].text

    await interaction.followup.send(f"**Session ended. Feedback:**\n{feedback}")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    active = session.get_session(message.channel.id)
    if active is None:
        return

    active.messages.append({"role": "user", "content": message.content})

    async with message.channel.typing():
        response = await anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=active.system_prompt,
            messages=active.messages,
        )
        reply_text = response.content[0].text
        active.messages.append({"role": "assistant", "content": reply_text})

        audio_file = None
        try:
            audio_buffer = voice.synthesize(reply_text)
            audio_file = discord.File(audio_buffer, filename="reply.mp3")
        except Exception as e:
            print(f"Voice synthesis failed: {e}")

        if audio_file:
            await message.channel.send(content=reply_text, file=audio_file)
        else:
            await message.channel.send(content=reply_text)


if __name__ == "__main__":
    client.run(os.environ["DISCORD_BOT_TOKEN"])
