# Sparked Practise Bot

A Discord bot for practising day-game cold approach. `/practise` starts a roleplay (Claude plays the woman, with ElevenLabs voice replies), and `/end` gives a feedback critique. Setup, env vars and run steps are in `README.md`, so don't duplicate them here.

## Files
- `bot.py`: Discord commands and the message loop.
- `persona.py`: her persona and the roleplay/critique prompts.
- `session.py`: per-channel conversation state.
- `voice.py`: ElevenLabs text-to-speech.

## Quality gates
- The generic `qa/` checks run automatically (syntax, imports resolve, no hardcoded secrets). Keys live only in `.env`, which is gitignored.
- After changing prompts in `persona.py`, run one short practice exchange before calling it done. Check that she stays in character, that her responses are realistic (not a pushover, not hostile), and that the critique is specific.

## Scope rules
- The Claude model ID is set in one place. When upgrading models, use the `claude-api` skill for current IDs rather than guessing.
- Separate product from the content pipeline. It doesn't read or write other folders.
