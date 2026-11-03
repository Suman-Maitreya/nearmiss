"""Batch-render + Spark-review the next 4 critical events from session 20250526."""
import os, subprocess, time, json, base64, sqlite3, datetime
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from nearmiss.physics import build_visits, pet_between, VEHICLE_TYPES

DB = r"D:\META\nearmiss\nearmiss.db"
BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
VIDEO = r"D:\META\nearmiss\data\fluid\videos\20250526_video.mp4"
SCENE = "20250526_video_Traj"
FRAME_W, FRAME_H = 3840, 2160
PIX_PER_M = 24.75
OFFSETS = [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0]

EVENTS_TO_PROCESS = [
    (897, 871),
    (768, 539),
    (1540, 1552),
    (1756, 1757),
]

def w2p(x_m, y_m):
    return (FRAME_W/2 + x_m * PIX_PER_M, FRAME_H/2 - y_m * PIX_PER_M)

print("[0/5] loading trajectory + font...")
traj = pd.read_csv(BASE + f"\\traj\\{SCENE}.csv",
                   usecols=['id','time','cx_m','cy_m','type','speed','length_med','width_med','course'])
try:
    font_big = ImageFont.truetype("arial.ttf", 48)
    font = ImageFont.truetype("arial.ttf", 36)
except OSError:
    font_big = font = ImageFont.load_default()

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])

NEUTRAL_PROMPT = ("You are reviewing a sequence of 7 top-down aerial surveillance frames of a road "
    "intersection, captured 1 second apart. Each frame has two overlays: a green circle labeled "
    "with a 'P' prefix, and an orange rectangle labeled with a 'V' prefix. These overlays mark "
    "positions of a pedestrian (P) and a vehicle (V) tracked across the sequence.\n\n"
    "Answer each question briefly and factually based ONLY on what you can see:\n\n"
    "1. In the frames where the P overlay is present, does it appear to be placed on top of a "
    "real pedestrian visible on the ground? (yes / no / unsure)\n"
    "2. In the frames where the V overlay is present, does it appear to be placed on top of a "
    "real moving vehicle (car / scooter / motorcycle) visible on the ground? (yes / no / unsure)\n"
    "3. Across the 7 frames, do the labeled pedestrian and labeled vehicle approach and come "
    "into very close proximity (within what looks like a vehicle's length)? (yes / no / unsure)\n"
    "4. In which frame number (0-6) do they appear closest? (integer 0-6, or 'unsure')\n"
    "5. Brief free-text observation (1-2 sentences)\n\n"
    "Reply as strict JSON matching this schema, no prose outside the JSON:\n"
    "{\n"
    '  "pedestrian_overlay_on_real_pedestrian": "yes|no|unsure",\n'
    '  "vehicle_overlay_on_real_vehicle":        "yes|no|unsure",\n'
    '  "paths_close":                             "yes|no|unsure",\n'
    '  "closest_frame":                           0-6 or "unsure",\n'
    '  "observation":                             "string"\n'
    "}")

def nearest_row(df, t):
    return df.iloc[(df['time']-t).abs().idxmin()]

def render_event(ped_id, veh_id):
    p = traj[traj['id']==ped_id].sort_values('time').reset_index(drop=True)
    v = traj[traj['id']==veh_id].sort_values('time').reset_index(drop=True)
    merged = pd.merge(p[['time','cx_m','cy_m']].rename(columns={'cx_m':'px','cy_m':'py'}),
                      v[['time','cx_m','cy_m']].rename(columns={'cx_m':'vx','cy_m':'vy'}),
                      on='time', how='inner')
    merged['dist'] = np.sqrt((merged['px']-merged['vx'])**2 + (merged['py']-merged['vy'])**2)
    t_conflict = float(merged.loc[merged['dist'].idxmin(), 'time'])
    d_conflict = float(merged['dist'].min())
    cx_m = (merged.loc[merged['dist'].idxmin(),'px'] + merged.loc[merged['dist'].idxmin(),'vx'])/2
    cy_m = (merged.loc[merged['dist'].idxmin(),'py'] + merged.loc[merged['dist'].idxmin(),'vy'])/2

    out_dir = rf"D:\META\nearmiss\runs\real_evidence_ped{ped_id}_veh{veh_id}"
    os.makedirs(out_dir, exist_ok=True)

    CROP_HALF_M = 25.0
    center_px, center_py = w2p(cx_m, cy_m)
    cph = CROP_HALF_M * PIX_PER_M
    crop_box = (max(0,int(center_px-cph)), max(0,int(center_py-cph)),
                min(FRAME_W,int(center_px+cph)), min(FRAME_H,int(center_py+cph)))

    def to_crop(x_m, y_m):
        gx, gy = w2p(x_m, y_m)
        return (gx - crop_box[0], gy - crop_box[1])

    for i, off in enumerate(OFFSETS):
        t = t_conflict + off
        tmp = os.path.join(out_dir, f"_raw_{i}.jpg")
        subprocess.run(["ffmpeg","-y","-loglevel","error","-ss",f"{t:.3f}","-i",VIDEO,"-vframes","1","-q:v","2",tmp], check=True)
        frame = Image.open(tmp).convert('RGB').crop(crop_box).copy()
        draw = ImageDraw.Draw(frame, 'RGBA')
        p_trail = p[(p['time']>=t-2)&(p['time']<=t)]
        v_trail = v[(v['time']>=t-2)&(v['time']<=t)]
        if len(p_trail)>=2:
            pts = [to_crop(x,y) for x,y in zip(p_trail['cx_m'], p_trail['cy_m'])]
            for a,b in zip(pts[:-1], pts[1:]): draw.line([a,b], fill=(0,220,60,200), width=6)
        if len(v_trail)>=2:
            pts = [to_crop(x,y) for x,y in zip(v_trail['cx_m'], v_trail['cy_m'])]
            for a,b in zip(pts[:-1], pts[1:]): draw.line([a,b], fill=(255,100,0,200), width=6)
        if p['time'].min() <= t <= p['time'].max():
            pr = nearest_row(p, t)
            px, py = to_crop(pr['cx_m'], pr['cy_m'])
            r = 18
            draw.ellipse([px-r,py-r,px+r,py+r], outline=(0,255,80), width=5)
            draw.text((px+22, py-20), f"P{ped_id}", fill=(0,255,80), font=font, stroke_width=3, stroke_fill=(0,0,0))
        if v['time'].min() <= t <= v['time'].max():
            vr = nearest_row(v, t)
            L = max(float(vr['length_med']) if np.isfinite(vr['length_med']) else 2.0, 3.5)
            W = max(float(vr['width_med']) if np.isfinite(vr['width_med']) else 1.5, 1.8)
            C = float(vr['course']) if np.isfinite(vr['course']) else 0.0
            vcx, vcy = to_crop(vr['cx_m'], vr['cy_m'])
            theta = np.deg2rad(C)
            hl, hw = L/2*PIX_PER_M, W/2*PIX_PER_M
            corners = np.array([[-hl,-hw],[hl,-hw],[hl,hw],[-hl,hw]])
            cos_t, sin_t = np.cos(theta), np.sin(theta)
            R_flip = np.array([[cos_t, sin_t],[sin_t, -cos_t]])
            corners_px = (corners @ R_flip.T) + np.array([vcx, vcy])
            draw.polygon([tuple(c) for c in corners_px], outline=(255,100,0), width=5)
            draw.text((vcx+22, vcy+22), f"V{veh_id}", fill=(255,100,0), font=font, stroke_width=3, stroke_fill=(0,0,0))
        draw.rectangle([(20,20),(420,100)], fill=(0,0,0,200))
        draw.text((35,32), f"t = {off:+.1f} s", fill=(255,255,255), font=font_big)
        out = os.path.join(out_dir, f"frame_{i:02d}_t{off:+.1f}s.jpg")
        frame.save(out, quality=90)
        os.remove(tmp)

    meta = {"scene": SCENE, "ped_id": ped_id, "veh_id": veh_id,
            "conflict_time_s": t_conflict, "closest_approach_m": d_conflict,
            "our_pet_s": 0.00, "severity": "critical", "render_mode": "real_video_frames",
            "frame_offsets_s": OFFSETS}
    with open(os.path.join(out_dir, "metadata.json"),"w") as f: json.dump(meta, f, indent=2)
    return out_dir, t_conflict, d_conflict

def spark_review(out_dir):
    frames_fns = [f"frame_{i:02d}_t{off:+.1f}s.jpg" for i, off in enumerate(OFFSETS)]
    image_parts = []
    for fn in frames_fns:
        with open(os.path.join(out_dir, fn), "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        image_parts.append({"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{data}"}})
    resp = client.chat.completions.create(
        model="muse-spark-1.3",
        messages=[{"role":"user","content":[{"type":"text","text":NEUTRAL_PROMPT}] + image_parts}],
        response_format={"type":"json_object"})
    return json.loads(resp.choices[0].message.content)

def decide(spark):
    paths = spark.get("paths_close")
    veh_ok = spark.get("vehicle_overlay_on_real_vehicle") == "yes"
    ped_ok = spark.get("pedestrian_overlay_on_real_pedestrian") == "yes"
    flags = []
    if spark.get("pedestrian_overlay_on_real_pedestrian") == "unsure": flags.append("ped_visibility_marginal_at_4K")
    if not veh_ok and spark.get("vehicle_overlay_on_real_vehicle") == "unsure": flags.append("veh_visibility_marginal_at_4K")
    if not veh_ok and spark.get("vehicle_overlay_on_real_vehicle") == "no": flags.append("spark_doubts_vehicle_overlay")
    if paths == "no":
        return "rejected", "Spark says paths not close", flags
    if paths == "unsure":
        return "unclear", "Spark unsure about paths closing", flags
    if paths == "yes" and veh_ok and ped_ok and not flags:
        return "supported", "All checks confirmed", flags
    return "supported_with_flag", f"Paths close confirmed; flags: {','.join(flags) if flags else 'ped_or_veh_marginal'}", flags

print(f"[1/5] processing {len(EVENTS_TO_PROCESS)} events...")
con = sqlite3.connect(DB)

for idx, (ped_id, veh_id) in enumerate(EVENTS_TO_PROCESS, 2):
    print(f"\n[{idx}/5] event ped{ped_id}/veh{veh_id}")
    t0 = time.time()
    out_dir, t_conflict, d_conflict = render_event(ped_id, veh_id)
    print(f"      rendered 7 frames in {time.time()-t0:.1f}s  (closest {d_conflict:.2f}m at t={t_conflict:.1f}s)")

    t0 = time.time()
    spark = spark_review(out_dir)
    print(f"      Spark reviewed in {time.time()-t0:.1f}s  closest_frame={spark.get('closest_frame')}  paths={spark.get('paths_close')}")
    status, reason, flags = decide(spark)
    print(f"      decision: {status} — {reason}")

    full = {"event":{"scene":SCENE,"ped_id":ped_id,"veh_id":veh_id,"our_pet_s":0.0,"render_mode":"real_video_frames"},
            "spark_response": spark}
    with open(os.path.join(out_dir,"spark_review.json"),"w") as f: json.dump(full,f,indent=2)
    now = datetime.datetime.utcnow().isoformat()
    event_id = f"{SCENE}_ped{ped_id}_veh{veh_id}"
    con.execute("""UPDATE events SET conflict_time_s=?, closest_approach_m=?, spark_status=?, spark_flags=?,
                   spark_observation=?, needs_human_review=?, evidence_dir=?, updated_at=? WHERE event_id=?""",
                (t_conflict, d_conflict, status, json.dumps(flags), spark.get("observation",""),
                 1 if status in ("supported_with_flag","unclear") else 0, out_dir, now, event_id))
    con.commit()
    print(f"      DB updated for {event_id}")

con.close()
print("\n[done] all events rendered and reviewed. Reload the dashboard.")
