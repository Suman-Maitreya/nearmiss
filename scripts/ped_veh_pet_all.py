"""Pedestrian-vehicle PET distribution across ALL FLUID sessions."""
import pandas as pd
import numpy as np
import os, sys, pathlib, time as _t
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from nearmiss.physics import build_visits, pet_between, VEHICLE_TYPES

BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
SCENES = ['20250120_video_Traj', '20250525_video_Traj', '20250526_video_Traj']

all_events = []
summary_rows = []

for scene in SCENES:
    print(f"\n=== {scene} ===")
    traj = pd.read_csv(BASE + f"\\traj\\{scene}.csv")
    peds = traj[traj['type']=='pedestrian']
    vehs = traj[traj['type'].isin(VEHICLE_TYPES)]
    ped_ids = peds['id'].unique()
    veh_ids = vehs['id'].unique()
    print(f"  peds={len(ped_ids)}  vehs={len(veh_ids)}  rows={len(traj):,}")

    t0 = _t.time()
    ped_visits = {int(pid): build_visits(traj[traj['id']==pid], use_footprint=False) for pid in ped_ids}
    veh_visits = {int(vid): build_visits(traj[traj['id']==vid], use_footprint=True) for vid in veh_ids}
    print(f"  visits built in {_t.time()-t0:.1f}s")

    # candidate filter
    ped_prof = {pid: (set(v.cell for v in vs), min(v.enter_t for v in vs), max(v.exit_t for v in vs)) for pid, vs in ped_visits.items() if vs}
    veh_prof = {vid: (set(v.cell for v in vs), min(v.enter_t for v in vs), max(v.exit_t for v in vs)) for vid, vs in veh_visits.items() if vs}
    candidates = []
    for pid, (pc, pt0, pt1) in ped_prof.items():
        for vid, (vc, vt0, vt1) in veh_prof.items():
            if vt1+5 < pt0 or pt1+5 < vt0: continue
            if not (pc & vc): continue
            candidates.append((pid, vid))

    scene_events = []
    for pid, vid in candidates:
        pet = pet_between(ped_visits[pid], veh_visits[vid])
        if pet is not None:
            scene_events.append({'scene': scene, 'ped_id': pid, 'veh_id': vid, 'pet_s': pet})
    print(f"  candidates={len(candidates)}  PETs<=2.0s={len(scene_events)}")

    all_events.extend(scene_events)
    scene_df = pd.DataFrame(scene_events)
    if len(scene_df):
        crit = (scene_df['pet_s']<=1.0).sum()
        ser  = ((scene_df['pet_s']>1.0)&(scene_df['pet_s']<=1.5)).sum()
        mod  = ((scene_df['pet_s']>1.5)&(scene_df['pet_s']<=2.0)).sum()
        summary_rows.append({'scene': scene, 'peds': len(ped_ids), 'vehs': len(veh_ids),
                             'events': len(scene_df), 'critical': crit, 'serious': ser, 'moderate': mod,
                             'min_pet': scene_df['pet_s'].min(), 'median_pet': scene_df['pet_s'].median()})

print("\n" + "="*70)
print("ALL-SESSION SUMMARY")
print("="*70)
smry = pd.DataFrame(summary_rows)
print(smry.to_string(index=False))

all_df = pd.DataFrame(all_events)
print(f"\nTOTAL across sessions: {len(all_df)} pedestrian-vehicle near-miss events")
print(f"  critical (<=1s): {(all_df['pet_s']<=1.0).sum()}")
print(f"  serious:         {((all_df['pet_s']>1.0)&(all_df['pet_s']<=1.5)).sum()}")
print(f"  moderate:        {((all_df['pet_s']>1.5)&(all_df['pet_s']<=2.0)).sum()}")

out_path = r"D:\META\nearmiss\runs\ped_veh_pet_ALL.csv"
all_df.to_csv(out_path, index=False)
print(f"\nSaved all events to {out_path}")
