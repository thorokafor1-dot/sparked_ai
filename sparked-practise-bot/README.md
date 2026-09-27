# Cold Approach Practice Bot

Discord bot for practising in-person cold approach conversation. `/practise` starts a session where the bot roleplays a woman being approached during the day; every message you send in that channel is treated as your side of the conversation, and her replies come back as text plus a spoken voice clip (ElevenLabs). `/end` closes the session and gives you a feedback critique.

## Setup

### 1. Discord bot
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, create a bot user, enable **Message Content Intent**, and copy the bot token into `.env` as `DISCORD_BOT_TOKEN`.
3. Under **OAuth2 > URL Generator**, select scopes `bot` and `applications.commands`, permissions `Send Messages`, `Read Message History`, `Attach Files`. Open the generated URL to invite the bot to your server.

### 2. Anthropic API key
Get a key from the [Anthropic Console](https://console.anthropic.com) and put it in `.env` as `ANTHROPIC_API_KEY`.

### 3. ElevenLabs
Get an API key from [ElevenLabs](https://elevenlabs.io), pick a voice from your Voice Library (or clone one), copy its Voice ID, and put both into `.env` as `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID`.

### 4. Install and run
```
cp .env.example .env   # then fill in the four values
pip install -r requirements.txt
python bot.py
```

## Usage
- `/practise [difficulty] [location]` — starts a session in the current channel. `difficulty` is `cold`, `neutral`, `warm`, or `receptive` (default `neutral`). `location` is free text (default: random daytime setting).
- Just type normally in the channel to talk to her.
- `/end` — ends the session and posts a feedback critique of the conversation.

Only one session can run per channel at a time.
