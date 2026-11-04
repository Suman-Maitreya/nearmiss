"""One-off discovery script -- find the right model id for Meta's voice/TTS
model under your hackathon API key, before we wire anything into the app.

We already know "muse-spark-1.3" works via this same base_url/key (used
throughout this project). This script just asks the API what else is
available and tries the most likely candidate names for text-to-speech, so
we don't guess blindly and burn time wiring the wrong model id.

Run from the repo root in your activated venv (same one with MODEL_API_KEY set):
    python scripts\\discover_voice_model.py
"""
import os
from openai import OpenAI

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])

print("=== 1. Listing all models visible to your API key ===")
voice_like = []
try:
    models = client.models.list()
    for m in models.data:
        mid = m.id
        tag = ""
        if any(k in mid.lower() for k in ["voice", "tts", "speech", "audio", "seamless"]):
            tag = "   <-- looks like a voice/TTS model"
            voice_like.append(mid)
        print(f"  {mid}{tag}")
except Exception as e:
    print(f"  models.list() failed or isn't supported: {e}")

print("\n=== 2. Trying a direct TTS call against likely candidate model names ===")
candidates = [
    "meta-voice-1", "meta-voicebox", "voicebox-1", "seamless-tts-1",
    "meta-tts-1", "audiobox-1", "audiocraft-1",
]
candidates = list(dict.fromkeys(voice_like + candidates))  # discovered names first, de-duped

working = []
for model_id in candidates:
    try:
        resp = client.audio.speech.create(
            model=model_id,
            voice="default",
            input="This is a test of the NearMiss voice feature.",
        )
        out_path = f"runs/_voice_test_{model_id.replace('/', '_')}.mp3"
        os.makedirs("runs", exist_ok=True)
        resp.stream_to_file(out_path) if hasattr(resp, "stream_to_file") else open(out_path, "wb").write(resp.read())
        print(f"  SUCCESS: {model_id} -> wrote {out_path}")
        working.append(model_id)
    except Exception as e:
        print(f"  {model_id}: failed ({type(e).__name__}: {str(e)[:120]})")

print("\n=== RESULT ===")
if working:
    print(f"Working TTS model id(s): {working}")
    print("Send me this output -- I'll wire the first working one into the Resident report.")
else:
    print("No candidate worked. Paste the FULL output of section 1 (model list) back to me --")
    print("the real model id is probably in there under a name we didn't guess.")
