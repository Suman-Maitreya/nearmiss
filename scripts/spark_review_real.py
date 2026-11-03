import os, json, base64, time
from openai import OpenAI

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])

EVENT_DIR = r"D:\META\nearmiss\runs\real_evidence_ped894_veh871"
FRAMES = [f"frame_{i:02d}_t{off:+.1f}s.jpg" for i, off in enumerate([-3.0,-2.0,-1.0,0.0,1.0,2.0,3.0])]

print("[1/3] encoding frames as base64")
image_parts = []
for fn in FRAMES:
    path = os.path.join(EVENT_DIR, fn)
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    image_parts.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{data}"}
    })
    print(f"      {fn}: {len(data)//1024} KB base64")

NEUTRAL_PROMPT = (
    "You are reviewing a sequence of 7 top-down aerial surveillance frames of a road "
    "intersection, captured 1 second apart. Each frame has two overlays: a green circle "
    "labeled with a 'P' prefix, and an orange rectangle labeled with a 'V' prefix. These "
    "overlays mark positions of a pedestrian (P) and a vehicle (V) tracked across the "
    "sequence.\n\n"
    "Answer each question briefly and factually based ONLY on what you can see:\n\n"
    "1. In the frames where the P overlay is present, does it appear to be placed on top "
    "of a real pedestrian visible on the ground? (yes / no / unsure)\n"
    "2. In the frames where the V overlay is present, does it appear to be placed on top "
    "of a real moving vehicle (car / scooter / motorcycle) visible on the ground? "
    "(yes / no / unsure)\n"
    "3. Across the 7 frames, do the labeled pedestrian and labeled vehicle approach and "
    "come into very close proximity (within what looks like a vehicle's length)? "
    "(yes / no / unsure)\n"
    "4. In which frame number (0-6) do they appear closest? (integer 0-6, or 'unsure')\n"
    "5. Brief free-text observation (1-2 sentences)\n\n"
    "Reply as strict JSON matching this schema, no prose outside the JSON:\n"
    "{\n"
    '  "pedestrian_overlay_on_real_pedestrian": "yes|no|unsure",\n'
    '  "vehicle_overlay_on_real_vehicle":        "yes|no|unsure",\n'
    '  "paths_close":                             "yes|no|unsure",\n'
    '  "closest_frame":                           0-6 or "unsure",\n'
    '  "observation":                             "string"\n'
    "}"
)

print(f"\n[2/3] calling Muse Spark with {len(image_parts)} real-video frames")
t0 = time.time()
resp = client.chat.completions.create(
    model="muse-spark-1.3",
    messages=[{
        "role": "user",
        "content": [{"type": "text", "text": NEUTRAL_PROMPT}] + image_parts
    }],
    response_format={"type": "json_object"},
)
elapsed = time.time()-t0
print(f"      Spark responded in {elapsed:.1f}s")

raw = resp.choices[0].message.content
print("\n[3/3] Spark raw response:")
print(raw)

try:
    parsed = json.loads(raw)
    print("\n--- parsed ---")
    for k, v in parsed.items():
        print(f"  {k}: {v}")
except json.JSONDecodeError as e:
    print(f"\n!!! JSON decode failed: {e}")
    parsed = {"raw": raw, "parse_error": str(e)}

OUT = os.path.join(EVENT_DIR, "spark_review.json")
with open(OUT, "w") as f:
    json.dump({
        "event": {"scene": "20250526_video_Traj", "ped_id": 894, "veh_id": 871,
                  "our_pet_s": 0.00, "render_mode": "real_video_frames"},
        "spark_response": parsed,
        "spark_elapsed_s": elapsed,
    }, f, indent=2)
print(f"\nsaved -> {OUT}")
