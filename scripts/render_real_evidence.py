import os, subprocess
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
VIDEO = r"D:\META\nearmiss\data\fluid\videos\20250526_video.mp4"
SCENE = "20250526_video_Traj"
PED_ID = 894
VEH_ID = 871
T_CONFLICT = 375.6
OUT_DIR = r"D:\META\nearmiss\runs\real_evidence_ped894_veh871"
os.makedirs(OUT_DIR, exist_ok=True)

# Transform (video-native, confirmed from grid overlay)
FRAME_W, FRAME_H = 3840, 2160
PIX_PER_M = 24.75   # calibrated via grid against TIF
def w2p(x_m, y_m):
    return (FRAME_W/2 + x_m * PIX_PER_M, FRAME_H/2 - y_m * PIX_PER_M)

print("[1/3] loading trajectory")
traj = pd.read_csv(BASE + f"\\traj\\{SCENE}.csv",
                   usecols=['id','time','cx_m','cy_m','type','speed','length_med','width_med','course'])
p = traj[traj['id']==PED_ID].sort_values('time').reset_index(drop=True)
v = traj[traj['id']==VEH_ID].sort_values('time').reset_index(drop=True)

offsets = [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0]

# Crop around conflict center (world (21, 2))
CROP_HALF_M = 25.0  # 50m x 50m visible, so pedestrians are big enough to see
center_px, center_py = w2p(21, 2)
crop_half_px = CROP_HALF_M * PIX_PER_M
crop_box = (int(center_px - crop_half_px), int(center_py - crop_half_px),
            int(center_px + crop_half_px), int(center_py + crop_half_px))
# clamp
crop_box = (max(0, crop_box[0]), max(0, crop_box[1]),
            min(FRAME_W, crop_box[2]), min(FRAME_H, crop_box[3]))

try:
    font_big = ImageFont.truetype("arial.ttf", 48)
    font = ImageFont.truetype("arial.ttf", 36)
except OSError:
    font_big = font = ImageFont.load_default()

print(f"[2/3] rendering {len(offsets)} frames to {OUT_DIR}")

def nearest_row(df, t):
    return df.iloc[(df['time']-t).abs().idxmin()]

PED_COLOR = (0,255,80)
VEH_COLOR = (255,100,0)

for i, off in enumerate(offsets):
    t = T_CONFLICT + off
    # extract this specific video frame to disk
    tmp = os.path.join(OUT_DIR, f"_raw_{i}.jpg")
    subprocess.run([
        "ffmpeg","-y","-loglevel","error",
        "-ss", f"{t:.3f}", "-i", VIDEO,
        "-vframes","1","-q:v","2", tmp
    ], check=True)
    frame = Image.open(tmp).convert('RGB').crop(crop_box).copy()
    draw = ImageDraw.Draw(frame, 'RGBA')

    def to_crop_pix(x_m, y_m):
        gx, gy = w2p(x_m, y_m)
        return (gx - crop_box[0], gy - crop_box[1])

    # trails (last 2s)
    p_trail = p[(p['time']>=t-2) & (p['time']<=t)]
    v_trail = v[(v['time']>=t-2) & (v['time']<=t)]
    if len(p_trail) >= 2:
        pts = [to_crop_pix(x,y) for x,y in zip(p_trail['cx_m'], p_trail['cy_m'])]
        for a,b in zip(pts[:-1], pts[1:]):
            draw.line([a,b], fill=(0,220,60,200), width=6)
    if len(v_trail) >= 2:
        pts = [to_crop_pix(x,y) for x,y in zip(v_trail['cx_m'], v_trail['cy_m'])]
        for a,b in zip(pts[:-1], pts[1:]):
            draw.line([a,b], fill=(255,100,0,200), width=6)

    # pedestrian: circle + label
    if p['time'].min() <= t <= p['time'].max():
        pr = nearest_row(p, t)
        px, py = to_crop_pix(pr['cx_m'], pr['cy_m'])
        r = 18
        draw.ellipse([px-r,py-r,px+r,py+r], outline=PED_COLOR, width=5)
        draw.text((px+22, py-20), f"P{PED_ID}", fill=PED_COLOR, font=font, stroke_width=3, stroke_fill=(0,0,0))

    # vehicle: oriented rect + label (inflate min size for visibility)
    if v['time'].min() <= t <= v['time'].max():
        vr = nearest_row(v, t)
        L = max(float(vr['length_med']) if np.isfinite(vr['length_med']) else 2.0, 3.5)
        W = max(float(vr['width_med'])  if np.isfinite(vr['width_med'])  else 1.5, 1.8)
        C = float(vr['course']) if np.isfinite(vr['course']) else 0.0
        vcx, vcy = to_crop_pix(vr['cx_m'], vr['cy_m'])
        theta = np.deg2rad(C)
        half_l = L/2 * PIX_PER_M
        half_w = W/2 * PIX_PER_M
        corners = np.array([[-half_l,-half_w],[half_l,-half_w],[half_l,half_w],[-half_l,half_w]])
        cos_t, sin_t = np.cos(theta), np.sin(theta)
        R_flip = np.array([[cos_t, sin_t],[sin_t, -cos_t]])
        corners_px = (corners @ R_flip.T) + np.array([vcx, vcy])
        draw.polygon([tuple(c) for c in corners_px], outline=VEH_COLOR, width=5)
        draw.text((vcx+22, vcy+22), f"V{VEH_ID}", fill=VEH_COLOR, font=font, stroke_width=3, stroke_fill=(0,0,0))

    # label
    draw.rectangle([(20,20),(420,100)], fill=(0,0,0,200))
    draw.text((35, 32), f"t = {off:+.1f} s", fill=(255,255,255), font=font_big)

    out = os.path.join(OUT_DIR, f"frame_{i:02d}_t{off:+.1f}s.jpg")
    frame.save(out, quality=90)
    os.remove(tmp)
    print(f"      saved {out}")

print("\n[3/3] metadata")
import json
meta = {
    "scene": SCENE, "ped_id": PED_ID, "veh_id": VEH_ID,
    "conflict_time_s": T_CONFLICT,
    "closest_approach_m": 1.3729530217745956,
    "our_pet_s": 0.00, "severity": "critical",
    "crop_center_world_m": [21.0, 2.0],
    "crop_half_m": CROP_HALF_M,
    "pix_per_m": PIX_PER_M,
    "frame_offsets_s": offsets,
    "source_video": VIDEO,
    "render_mode": "real_video_frames",
}
with open(os.path.join(OUT_DIR, "metadata.json"), "w") as f:
    json.dump(meta, f, indent=2)
print(f"      metadata.json written  ->  {OUT_DIR}")
