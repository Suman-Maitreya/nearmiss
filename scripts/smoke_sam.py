import os, re, time
from openai import OpenAI

CLIP = r"D:\META\nearmiss\data\tad\01_Accident_022_first300.mp4"
CONCEPT = "pedestrian"
OUT_RAW = r"D:\META\nearmiss\scripts\sam_smoke_raw.txt"

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])

print("[1/3] uploading clip:", CLIP)
t0 = time.time()
with open(CLIP, "rb") as f:
    up = client.files.create(purpose="user_data", file=f)
print(f"      file_id={up.id} status={up.status}  (upload {time.time()-t0:.1f}s)")

print(f"[2/3] running SAM 3.1 with concept: '{CONCEPT}'")
t0 = time.time()
raw_lines = []
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
        delta = getattr(event, "delta", None)
        if delta:
            raw_lines.append(delta)

raw = "".join(raw_lines)
with open(OUT_RAW, "w", encoding="utf-8") as f:
    f.write(raw)
print(f"      done in {time.time()-t0:.1f}s, {len(raw)} chars written to {OUT_RAW}")

print("[3/3] parsing summary")
frame_markers = re.findall(r"<(\d+)f>", raw)
frames_with_dets = set(int(m) for m in frame_markers)
boxes = re.findall(r"<\|box;", raw)
obj_ids_per_frame = re.findall(r"<(\d+)f>\s*(\d+)", raw)
unique_frames = len(frames_with_dets)
total_boxes = len(boxes)
first_frame_det = min(frames_with_dets) if frames_with_dets else None
last_frame_det  = max(frames_with_dets) if frames_with_dets else None

print(f"      frames with >=1 detection: {unique_frames} / 300")
print(f"      total box annotations: {total_boxes}")
print(f"      first/last frame with detection: {first_frame_det} / {last_frame_det}")
print(f"      first 500 chars of raw stream:")
print("      " + raw[:500].replace("\n","\n      "))
