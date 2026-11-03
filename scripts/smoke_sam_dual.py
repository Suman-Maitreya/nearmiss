import os, re, time
from openai import OpenAI

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])

TESTS = [
    ("car",    r"D:\META\nearmiss\data\tad\01_Accident_022_first300.mp4", "sam_test_car.txt"),
    ("person", r"D:\META\nearmiss\data\tad\01_Accident_022_f600_909.mp4", "sam_test_person.txt"),
]

def run(concept, clip_path, out_file):
    print(f"\n=== concept='{concept}'  clip={os.path.basename(clip_path)} ===")
    t0 = time.time()
    with open(clip_path, "rb") as f:
        up = client.files.create(purpose="user_data", file=f)
    print(f"  uploaded  file_id={up.id}  ({time.time()-t0:.1f}s)")

    t0 = time.time()
    chunks = []
    with client.responses.stream(
        model="sam-3.1",
        input=[{
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": concept},
                {"type": "input_video", "file_id": up.id},
            ],
        }],
    ) as stream:
        for event in stream:
            delta = getattr(event, "delta", None)
            if isinstance(delta, str):
                chunks.append(delta)
        final = stream.get_final_response()

    raw = "".join(chunks)
    if not raw:
        try:
            raw = final.output[0].content[0].text or ""
        except Exception:
            raw = ""

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(raw)

    frames = set(int(m) for m in re.findall(r"<(\d+)f>", raw))
    boxes = len(re.findall(r"<\|box;", raw))
    print(f"  SAM done {time.time()-t0:.1f}s  raw_chars={len(raw)}  frames_with_detections={len(frames)}  total_boxes={boxes}")
    if frames:
        print(f"  frame range: {min(frames)}..{max(frames)}")
        print(f"  first 300 chars of stream:")
        print("    " + raw[:300].replace("\n","\n    "))
    else:
        print("  (no detections)")
        print(f"  saved raw to {out_file}")

for concept, path, out in TESTS:
    run(concept, path, out)
