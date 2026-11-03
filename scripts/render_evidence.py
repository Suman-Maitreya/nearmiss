import os
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
SCENE = "20250526_video_Traj"
PED_ID = 894
VEH_ID = 871

# TIF georeference (metres, from rasterio check)
TIF_PATH = BASE + r"\map\FIDRT.tif"
WORLD_LEFT = -72.94104142615106
WORLD_TOP  =  47.5109209776856
PIX_PER_M  = 25.0   # 0.04 m per pixel -> 25 pixels per metre

def world_to_pixel(x_m, y_m):
    px = (x_m - WORLD_LEFT) * PIX_PER_M
    py = (WORLD_TOP - y_m) * PIX_PER_M
    return (px, py)

print("[1/4] loading trajectory + TIF")
traj = pd.read_csv(BASE + f"\\traj\\{SCENE}.csv",
                   usecols=['id','time','cx_m','cy_m','type','speed','length_med','width_med','course'])
p = traj[traj['id']==PED_ID].sort_values('time').reset_index(drop=True)
v = traj[traj['id']==VEH_ID].sort_values('time').reset_index(drop=True)
print(f"      ped track: {len(p)} pts  [{p['time'].min():.1f}, {p['time'].max():.1f}] s")
print(f"      veh track: {len(v)} pts  [{v['time'].min():.1f}, {v['time'].max():.1f}] s")

# find closest-approach time
merged = pd.merge(p[['time','cx_m','cy_m']].rename(columns={'cx_m':'px','cy_m':'py'}),
                  v[['time','cx_m','cy_m']].rename(columns={'cx_m':'vx','cy_m':'vy'}),
                  on='time', how='inner')
merged['dist'] = np.sqrt((merged['px']-merged['vx'])**2 + (merged['py']-merged['vy'])**2)
t_conflict = float(merged.loc[merged['dist'].idxmin(), 'time'])
d_conflict = float(merged['dist'].min())
print(f"      conflict at t={t_conflict:.1f}s, closest={d_conflict:.2f} m")

tif = Image.open(TIF_PATH).convert('RGB')
print(f"      TIF loaded: {tif.size}")

# Crop around conflict center: 40m x 40m window
CROP_HALF_M = 20.0
# center of crop = midpoint between ped and veh at t_conflict
cx_m = (merged.loc[merged['dist'].idxmin(), 'px'] + merged.loc[merged['dist'].idxmin(), 'vx']) / 2
cy_m = (merged.loc[merged['dist'].idxmin(), 'py'] + merged.loc[merged['dist'].idxmin(), 'vy']) / 2
center_px, center_py = world_to_pixel(cx_m, cy_m)
crop_half_px = CROP_HALF_M * PIX_PER_M
crop_box = (int(center_px - crop_half_px), int(center_py - crop_half_px),
            int(center_px + crop_half_px), int(center_py + crop_half_px))
print(f"      crop center world=({cx_m:.2f},{cy_m:.2f})  pixel=({center_px:.0f},{center_py:.0f})")
print(f"      crop box: {crop_box}")

# frames to render: t-3, t-2, t-1, t, t+1, t+2, t+3
offsets = [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0]
out_dir = r"D:\META\nearmiss\runs\evidence_event_ped894_veh871"
os.makedirs(out_dir, exist_ok=True)

print(f"\n[2/4] rendering {len(offsets)} frames to {out_dir}")

# color constants
PED_COLOR = (0, 220, 60)      # bright green
VEH_COLOR = (255, 60, 0)      # bright red-orange
PED_TRAIL = (0, 180, 50, 140) # with alpha hint
VEH_TRAIL = (255, 100, 0, 140)

try:
    font = ImageFont.truetype("arial.ttf", 28)
    font_small = ImageFont.truetype("arial.ttf", 18)
except OSError:
    font = ImageFont.load_default()
    font_small = font

def nearest_row(df, t):
    i = (df['time'] - t).abs().idxmin()
    return df.loc[i]

def to_crop_pix(x_m, y_m):
    gx, gy = world_to_pixel(x_m, y_m)
    return (gx - crop_box[0], gy - crop_box[1])

for i, off in enumerate(offsets):
    t = t_conflict + off
    frame = tif.crop(crop_box).copy()
    draw = ImageDraw.Draw(frame, 'RGBA')

    # ped & veh trails over last 2 seconds leading up to this frame
    p_trail = p[(p['time']>=t-2) & (p['time']<=t)]
    v_trail = v[(v['time']>=t-2) & (v['time']<=t)]

    if len(p_trail) >= 2:
        pts = [to_crop_pix(x,y) for x,y in zip(p_trail['cx_m'], p_trail['cy_m'])]
        for a,b in zip(pts[:-1], pts[1:]):
            draw.line([a,b], fill=PED_TRAIL, width=4)
    if len(v_trail) >= 2:
        pts = [to_crop_pix(x,y) for x,y in zip(v_trail['cx_m'], v_trail['cy_m'])]
        for a,b in zip(pts[:-1], pts[1:]):
            draw.line([a,b], fill=VEH_TRAIL, width=4)

    # current ped position (if ped exists at t)
    if p['time'].min() <= t <= p['time'].max():
        pr = nearest_row(p, t)
        px, py = to_crop_pix(pr['cx_m'], pr['cy_m'])
        r = 8
        draw.ellipse([px-r,py-r,px+r,py+r], fill=PED_COLOR, outline=(0,0,0), width=2)
        draw.text((px+12, py-10), f"P{PED_ID}", fill=PED_COLOR, font=font_small, stroke_width=2, stroke_fill=(0,0,0))

    # current vehicle: oriented rectangle
    if v['time'].min() <= t <= v['time'].max():
        vr = nearest_row(v, t)
        L = float(vr['length_med']) if np.isfinite(vr['length_med']) else 2.0
        W = float(vr['width_med']) if np.isfinite(vr['width_med']) else 1.5
        C = float(vr['course']) if np.isfinite(vr['course']) else 0.0
        vcx, vcy = to_crop_pix(vr['cx_m'], vr['cy_m'])
        theta = np.deg2rad(C)
        half_l_px = L/2 * PIX_PER_M
        half_w_px = W/2 * PIX_PER_M
        # rectangle corners in local frame
        corners_local = np.array([[-half_l_px,-half_w_px],[half_l_px,-half_w_px],
                                  [half_l_px,half_w_px],[-half_l_px,half_w_px]])
        cos_t, sin_t = np.cos(theta), np.sin(theta)
        R = np.array([[cos_t,-sin_t],[sin_t,cos_t]])
        corners_px = (corners_local @ R.T) + np.array([vcx, vcy])
        # note: TIF Y is flipped vs trajectory Y, but course is in traj frame.
        # Our y-axis in pixels increases downward, in world increases upward.
        # Reflect y when going from world rotation to pixel rotation:
        corners_local_flip = np.array([[-half_l_px,-half_w_px],[half_l_px,-half_w_px],
                                       [half_l_px,half_w_px],[-half_l_px,half_w_px]])
        R_flip = np.array([[cos_t, sin_t],[sin_t, -cos_t]])
        corners_px = (corners_local_flip @ R_flip.T) + np.array([vcx, vcy])
        pts = [tuple(c) for c in corners_px]
        draw.polygon(pts, outline=VEH_COLOR, width=3)
        draw.text((vcx+12, vcy-10), f"V{VEH_ID}", fill=VEH_COLOR, font=font_small, stroke_width=2, stroke_fill=(0,0,0))

    # top-left overlay with time
    label = f"t = {off:+.1f} s"
    draw.rectangle([(10,10),(240,55)], fill=(0,0,0,180))
    draw.text((20, 15), label, fill=(255,255,255), font=font)

    out = os.path.join(out_dir, f"frame_{i:02d}_t{off:+.1f}s.jpg")
    frame.save(out, quality=92)
    print(f"      saved {out}")

print("\n[3/4] metadata")
import json
meta = {
    "scene": SCENE,
    "ped_id": PED_ID,
    "veh_id": VEH_ID,
    "conflict_time_s": t_conflict,
    "closest_approach_m": d_conflict,
    "our_pet_s": 0.00,
    "severity": "critical",
    "crop_center_world_m": [cx_m, cy_m],
    "crop_half_m": CROP_HALF_M,
    "frame_offsets_s": offsets,
    "tif_source": TIF_PATH,
}
with open(os.path.join(out_dir, "metadata.json"), "w") as f:
    json.dump(meta, f, indent=2)
print(f"      metadata.json written")

print(f"\n[4/4] open folder: {out_dir}")
