"""Test the REAL Meta ASR endpoint (from dev.meta.ai/docs/speech-to-text):
    POST https://api.meta.ai/v1/asr/transcribe
Multipart upload, Authorization: Bearer <key> header. Not the OpenAI client's
audio.transcriptions (that hits a different path and doesn't exist on this API).

Run:
    python scripts\\test_asr_transcribe.py test_tone.wav
"""
import os, sys, json, requests

if len(sys.argv) < 2:
    print("Usage: python scripts\\test_asr_transcribe.py <path-to-wav>")
    sys.exit(1)

audio_path = sys.argv[1]
key = os.environ["MODEL_API_KEY"]

request_obj = {"mode": "DIARIZATION", "model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV"}
print(f"\n--- trying: exact docs shape = {request_obj} ---")
with open(audio_path, "rb") as f:
    resp = requests.post(
        "https://api.meta.ai/v1/asr/transcribe?sessionId=nearmiss-test",
        headers={"Authorization": f"Bearer {key}"},
        files={
            "audio": (os.path.basename(audio_path), f, "audio/wav"),
            "request": (None, json.dumps(request_obj), "application/json"),
        },
        timeout=30,
    )
print(f"  HTTP {resp.status_code}")
print(f"  body: {resp.text[:800]}")

print("\n=== Paste this ENTIRE output back to me ===")
