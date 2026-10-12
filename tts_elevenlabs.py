import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

api_key = os.getenv("ELEVENLABS_API_KEY")
voice_id = os.getenv("ELEVENLABS_VOICE_ID")

if not api_key or not voice_id:
    raise ValueError("Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in .env")

client = ElevenLabs(api_key=api_key)

text = """
Well, this was very helpful. Please guide me on the transactions process at the branch.
"""

audio_stream = client.text_to_speech.convert(
    text=text.strip(),
    voice_id=voice_id,
    model_id="eleven_multilingual_v2",  # Good for English + Indian languages
    output_format="mp3_44100_128",
)

with open("output.mp3", "wb") as f:
    for chunk in audio_stream:
        if chunk:
            f.write(chunk)

print("Saved generated audio to output.mp3")