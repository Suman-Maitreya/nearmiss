"""Find the correct API call shape for muse-voice-transcribe-1.0.

We confirmed the model id exists (it showed up in client.models.list()), but
client.audio.transcriptions.create(...) returns 404 -- meaning this custom
API almost certainly doesn't implement OpenAI's separate /audio/transcriptions
REST route, same as it doesn't expose separate routes for the other muse-*
models. Spark and SAM are both called through chat.completions.create with
multimodal content parts (image_url). This script tries the most likely
chat.completions shapes for audio instead, against a tiny real recording,
and reports which one (if any) actually works.

Run from the repo root in your activated venv:
    python scripts\\discover_voice_api_shape.py "path\\to\\a\\short\\recording.wav"

If you don't have a wav file handy, it will also accept the most recent
voice note you recorded in the Review Queue -- Streamlit doesn't save those
to disk by default, so easiest is: record a 2-3 second note on your phone or
Voice Recorder app, save as .wav, and pass its path here.
"""
import os, sys, json, base64
from openai import OpenAI

if len(sys.argv) < 2:
    print("Usage: python scripts\\discover_voice_api_shape.py <path-to-wav-or-mp3>")
    sys.exit(1)

audio_path = sys.argv[1]
with open(audio_path, "rb") as f:
    audio_bytes = f.read()
b64 = base64.b64encode(audio_bytes).decode("ascii")
ext = os.path.splitext(audio_path)[1].lstrip(".").lower() or "wav"

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])
MODEL = "muse-voice-transcribe-1.0"

attempts = []

# Shape A: OpenAI's newer audio-chat content part ("input_audio")
attempts.append(("input_audio content part", lambda: client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "Transcribe this audio exactly, reply with only the transcript text."},
        {"type": "input_audio", "input_audio": {"data": b64, "format": ext}},
    ]}],
)))

# Shape B: data-URI style audio_url, mirroring how we pass image_url elsewhere in this project
attempts.append(("audio_url data-URI content part", lambda: client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "Transcribe this audio exactly, reply with only the transcript text."},
        {"type": "audio_url", "audio_url": {"url": f"data:audio/{ext};base64,{b64}"}},
    ]}],
)))

# Shape C: client.audio.translations (different OpenAI audio endpoint, just in case)
attempts.append(("audio.translations.create", lambda: client.audio.translations.create(
    model=MODEL, file=open(audio_path, "rb"),
)))

# Shape D: raw multipart REST POST to /audio/transcriptions, bypassing the python client,
# in case the client library's route differs from the server's actual route.
import requests
attempts.append(("raw POST /audio/transcriptions", lambda: requests.post(
    "https://api.meta.ai/v1/audio/transcriptions",
    headers={"Authorization": f"Bearer {os.environ['MODEL_API_KEY']}"},
    files={"file": (os.path.basename(audio_path), open(audio_path, "rb"))},
    data={"model": MODEL},
    timeout=30,
)))

for name, fn in attempts:
    print(f"\n--- trying: {name} ---")
    try:
        result = fn()
        if hasattr(result, "status_code"):  # raw requests.Response
            print(f"  HTTP {result.status_code}")
            print(f"  body: {result.text[:400]}")
            if result.ok:
                print(f"  SUCCESS via {name}")
        else:
            text = getattr(result, "text", None)
            if text is None and hasattr(result, "choices"):
                text = result.choices[0].message.content
            print(f"  SUCCESS via {name}")
            print(f"  transcript: {text}")
    except Exception as e:
        print(f"  failed: {type(e).__name__}: {str(e)[:200]}")

print("\n=== Paste this ENTIRE output back to me ===")
