"""Pedestrian-vehicle PET distribution on FLUID session 20250120.

Architecture 2.1 §16 Step 6 demo-relevant output.
"""
import pandas as pd
import numpy as np
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from nearmiss.physics import build_visits, pet_between, VEHICLE_TYPES

BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
SCENE = "20250120_video_Traj"

print("[1/5] loading trajectory")
traj = pd.read_csv(BASE + f"\\traj\\{SCENE}.csv")
print(f"      total rows: {len(traj):,}")
print(f"      unique ids: {traj['id'].nunique():,}")

peds = traj[traj['type']=='pedestrian']
vehs = traj[traj['type'].isin(VEHICLE_TYPES)]
ped_ids = peds['id'].unique()
veh_ids = vehs['id'].unique()
print(f"      pedestrians: {len(ped_ids)}  vehicles: {len(veh_ids)}")

print("\n[2/5] building visits for all pedestrians and all vehicles")
print("      (this is the heavy step; ~1-3 min)")
import time as _t
t0 = _t.time()

ped_visits = {}
for pid in ped_ids:
    sub = traj[traj['id']==pid]
    ped_visits[int(pid)] = build_visits(sub, use_footprint=False)
print(f"      pedestrian visits done  ({_t.time()-t0:.1f}s)")

t0 = _t.time()
veh_visits = {}
for vid in veh_ids:
    sub = traj[traj['id']==vid]
    veh_visits[int(vid)] = build_visits(sub, use_footprint=True)
print(f"      vehicle visits done     ({_t.time()-t0:.1f}s)")

print("\n[3/5] filtering candidate pairs by cell-set intersection + time overlap")
t0 = _t.time()
# Pre-compute: for each ped, (cell_set, time_min, time_max)
ped_profiles = {}
for pid, vs in ped_visits.items():
    if not vs: continue
    cells = set(v.cell for v in vs)
    tmin = min(v.enter_t for v in vs)
    tmax = max(v.exit_t for v in vs)
    ped_profiles[pid] = (cells, tmin, tmax)
veh_profiles = {}
for vid, vs in veh_visits.items():
    if not vs: continue
    cells = set(v.cell for v in vs)
    tmin = min(v.enter_t for v in vs)
    tmax = max(v.exit_t for v in vs)
    veh_profiles[vid] = (cells, tmin, tmax)

candidates = []
for pid, (p_cells, p_t0, p_t1) in ped_profiles.items():
    for vid, (v_cells, v_t0, v_t1) in veh_profiles.items():
        # must overlap in time (within +/-5s window; vehicle before or after ped counts)
        if v_t1 + 5 < p_t0 or p_t1 + 5 < v_t0:
            continue
        if not (p_cells & v_cells):
            continue
        candidates.append((pid, vid))
print(f"      candidate pedestrian-vehicle pairs: {len(candidates)}  ({_t.time()-t0:.1f}s)")

print("\n[4/5] computing PET per candidate pair")
t0 = _t.time()
results = []
for pid, vid in candidates:
    pet = pet_between(ped_visits[pid], veh_visits[vid])
    if pet is not None:
        results.append({'ped_id': pid, 'veh_id': vid, 'pet_s': pet})
res = pd.DataFrame(results)
print(f"      pairs with PET<=2.0s: {len(res)}  ({_t.time()-t0:.1f}s)")

print("\n[5/5] distribution and severity banding")
if len(res):
    print(f"      PET distribution (s):")
    print(f"        min:    {res['pet_s'].min():.2f}")
    print(f"        p25:    {res['pet_s'].quantile(0.25):.2f}")
    print(f"        median: {res['pet_s'].median():.2f}")
    print(f"        p75:    {res['pet_s'].quantile(0.75):.2f}")
    print(f"        max:    {res['pet_s'].max():.2f}")

    def band(p):
        if p <= 1.0: return 'critical'
        if p <= 1.5: return 'serious'
        if p <= 2.0: return 'moderate'
        return 'other'
    res['severity'] = res['pet_s'].apply(band)
    print(f"\n      severity bands:")
    for b, n in res['severity'].value_counts().items():
        print(f"        {b:<10}: {n:>4}")

    print(f"\n      unique pedestrians involved: {res['ped_id'].nunique()}")
    print(f"      unique vehicles involved:    {res['veh_id'].nunique()}")

    # per-pedestrian worst PET
    worst = res.loc[res.groupby('ped_id')['pet_s'].idxmin()][['ped_id','veh_id','pet_s','severity']]
    worst = worst.sort_values('pet_s').reset_index(drop=True)
    print(f"\n      pedestrians with closest encounters (worst 10):")
    print(worst.head(10).to_string(index=False))

    out_path = r"D:\META\nearmiss\runs\ped_veh_pet_20250120.csv"
    import os
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    res.to_csv(out_path, index=False)
    print(f"\n      full table saved to {out_path}")
else:
    print("      no pedestrian-vehicle PETs under 2.0s — unexpected; investigate")
