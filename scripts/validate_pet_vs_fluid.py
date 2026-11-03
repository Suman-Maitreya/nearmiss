"""Score our grid-based PET implementation against FLUIDs 147 published conflicts.

Architecture 2.1 §16 Step 6 + Phase 2 evaluation gate.
"""
import pandas as pd
import numpy as np
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from nearmiss.physics import pairwise_pet

BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"

print("[1/4] loading FLUID conflicts (ground truth)")
conf = pd.read_csv(BASE + r"\conflict\FIDRT_conflict.csv")
print(f"      {len(conf)} published conflicts")
print(f"      scenes: {dict(conf['Scene'].value_counts())}")
print(f"      conflict types: {dict(conf['conflict_type'].value_counts())}")
print(f"      DGT/PET distribution: min={conf['DGT/PET'].min():.2f} median={conf['DGT/PET'].median():.2f} max={conf['DGT/PET'].max():.2f}")

# focus on session 20250120 for the first comparison
SCENE = "20250120_video_Traj"
conf_s = conf[conf['Scene'] == SCENE].copy()
print(f"\n      focusing on scene '{SCENE}': {len(conf_s)} conflicts")

print("\n[2/4] loading matching trajectory")
traj = pd.read_csv(BASE + f"\\traj\\{SCENE}.csv")
print(f"      {len(traj):,} rows, {traj['id'].nunique():,} unique ids")

print("\n[3/4] computing our PET for each labelled pair")
pairs = list(zip(conf_s['Car 1 ID'].astype(int), conf_s['Car 2 ID'].astype(int)))
our_pet = pairwise_pet(traj, pairs)

conf_s = conf_s.reset_index(drop=True)
conf_s['our_pet'] = [our_pet[(int(a), int(b))] for a, b in pairs]

matched = conf_s.dropna(subset=['our_pet']).copy()
missed = conf_s[conf_s['our_pet'].isna()]
print(f"      pairs we found sharing a cell: {len(matched)} / {len(conf_s)}")
print(f"      pairs we missed:               {len(missed)}")

print("\n[4/4] agreement with FLUID DGT/PET")
if len(matched):
    matched['abs_err'] = (matched['our_pet'] - matched['DGT/PET']).abs()
    print(f"      median |our_pet - DGT/PET|: {matched['abs_err'].median():.3f} s")
    print(f"      mean   |our_pet - DGT/PET|: {matched['abs_err'].mean():.3f} s")
    print(f"      max    |our_pet - DGT/PET|: {matched['abs_err'].max():.3f} s")
    within_025 = (matched['abs_err'] <= 0.25).sum()
    within_050 = (matched['abs_err'] <= 0.50).sum()
    print(f"      within 0.25s: {within_025} / {len(matched)}  ({100*within_025/len(matched):.0f}%)")
    print(f"      within 0.50s: {within_050} / {len(matched)}  ({100*within_050/len(matched):.0f}%)")

    print("\n      sample side-by-side (first 15):")
    cols = ['Frame', 'Car 1 ID', 'Car 2 ID', 'DGT/PET', 'our_pet', 'conflict_type']
    print(matched[cols].head(15).to_string(index=False))
else:
    print("      !!! no overlaps found — algorithm or coord-column mismatch — investigate")

if len(missed) > 0:
    print(f"\n      missed samples (first 5) — these pairs did not share any 0.5m cell within 2.0s:")
    print(missed[['Frame','Car 1 ID','Car 2 ID','DGT/PET','conflict_type']].head(5).to_string(index=False))
