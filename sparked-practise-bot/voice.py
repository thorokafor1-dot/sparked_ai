import io
import os

from elevenlabs.client import ElevenLabs

_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
_voice_id = os.environ["ELEVENLABS_VOICE_ID"]


def synthesize(text: str) -> io.BytesIO:
    audio = _client.text_to_speech.convert(
        voice_id=_voice_id,
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
    )
    buffer = io.BytesIO()
    for chunk in audio:
        buffer.write(chunk)
    buffer.seek(0)
    return buffer
