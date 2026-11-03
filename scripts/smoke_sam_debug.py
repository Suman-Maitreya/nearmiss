import os, time, json
from openai import OpenAI

CLIP = r"D:\META\nearmiss\data\tad\01_Accident_022_first300.mp4"
CONCEPT = "pedestrian"
OUT_RAW = r"D:\META\nearmiss\scripts\sam_smoke_raw.txt"
OUT_EVENTS = r"D:\META\nearmiss\scripts\sam_smoke_events.txt"

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])

print("[1/3] uploading clip:", CLIP)
with open(CLIP, "rb") as f:
    up = client.files.create(purpose="user_data", file=f)
print(f"      file_id={up.id} status={up.status}")

print(f"[2/3] streaming SAM 3.1 with concept: '{CONCEPT}'  (instrumented)")
t0 = time.time()
event_type_counts = {}
raw_chunks = []
sample_events = []

with client.responses.stream(
    model="sam-3.1",
    input=[{
        "type": "message",
        "role": "user",
        "content": [
            {"type": "input_text", "text": CONCEPT},
            {"type": "input_video", "file_id": up.id},
        ],
    }],
) as stream:
    for event in stream:
        et = getattr(event, "type", type(event).__name__)
        event_type_counts[et] = event_type_counts.get(et, 0) + 1
        if len(sample_events) < 20:
            try:
                sample_events.append((et, repr(event)[:400]))
            except Exception:
                sample_events.append((et, "<unreprable>"))
        delta = getattr(event, "delta", None)
        if isinstance(delta, str):
            raw_chunks.append(delta)

    final = stream.get_final_response()

elapsed = time.time() - t0
raw = "".join(raw_chunks)
with open(OUT_RAW, "w", encoding="utf-8") as f:
    f.write(raw)
with open(OUT_EVENTS, "w", encoding="utf-8") as f:
    f.write("event_type_counts:\n")
    for k, v in sorted(event_type_counts.items(), key=lambda x: -x[1]):
        f.write(f"  {k}: {v}\n")
    f.write("\nsample events (first 20):\n")
    for et, body in sample_events:
        f.write(f"  [{et}] {body}\n")
    f.write("\nfinal response:\n")
    try:
        f.write(json.dumps(final.model_dump(), indent=2, default=str))
    except Exception as e:
        f.write(f"(could not serialize final: {e})\n")
        f.write(repr(final))

print(f"      elapsed: {elapsed:.1f}s")
print(f"      event_type_counts: {event_type_counts}")
print(f"      raw delta chars: {len(raw)}")
print()
print("--- final response summary ---")
try:
    out = final.output
    print(f"      output items: {len(out)}")
    for i, item in enumerate(out[:3]):
        print(f"      [{i}] type={getattr(item,'type',None)}")
        if hasattr(item, 'content'):
            for j, c in enumerate(item.content[:3]):
                ct = getattr(c, 'type', None)
                text_preview = getattr(c, 'text', None)
                if text_preview:
                    text_preview = text_preview[:300]
                print(f"          content[{j}] type={ct} text={text_preview!r}")
except Exception as e:
    print(f"      (could not inspect final.output: {e})")

print()
print(f"Full event dump saved to: {OUT_EVENTS}")
