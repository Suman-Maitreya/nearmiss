import pandas as pd
import numpy as np
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from nearmiss.physics import pairwise_pet

BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
SCENES = ['20250120_video_Traj', '20250525_video_Traj', '20250526_video_Traj']

conf = pd.read_csv(BASE + r"\conflict\FIDRT_conflict.csv")
print(f"loaded {len(conf)} published conflicts across {len(SCENES)} scenes")

all_rows = []
for scene in SCENES:
    conf_s = conf[conf['Scene']==scene].reset_index(drop=True)
    if len(conf_s)==0: continue
    traj = pd.read_csv(BASE + f"\\traj\\{scene}.csv")
    pairs = list(zip(conf_s['Car 1 ID'].astype(int), conf_s['Car 2 ID'].astype(int)))
    our = pairwise_pet(traj, pairs)
    conf_s['our_pet'] = [our[(int(a),int(b))] for a,b in pairs]
    conf_s['scene'] = scene
    all_rows.append(conf_s)
    print(f"  {scene}: {len(conf_s)} conflicts, matched {conf_s['our_pet'].notna().sum()}")

res = pd.concat(all_rows, ignore_index=True)
matched = res.dropna(subset=['our_pet']).copy()
matched['abs_err'] = (matched['our_pet'] - matched['DGT/PET']).abs()

print(f"\nOVERALL: {len(matched)}/{len(res)} matched ({100*len(matched)/len(res):.0f}%)")
print(f"Overall median abs error: {matched['abs_err'].median():.3f}s")
print()

print("BY CONFLICT TYPE:")
print(f"{'type':<12} {'n_total':>8} {'n_matched':>10} {'match%':>7} {'median_err':>11} {'within_0.5s':>12}")
for ct in sorted(res['conflict_type'].unique()):
    sub = res[res['conflict_type']==ct]
    sub_matched = matched[matched['conflict_type']==ct]
    n_t = len(sub); n_m = len(sub_matched)
    if n_m > 0:
        med = sub_matched['abs_err'].median()
        wi = (sub_matched['abs_err']<=0.5).sum()
        print(f"{ct:<12} {n_t:>8} {n_m:>10} {100*n_m/n_t:>6.0f}% {med:>10.3f}s {wi}/{n_m:<4}  ({100*wi/n_m:.0f}%)")
    else:
        print(f"{ct:<12} {n_t:>8} {n_m:>10} {100*n_m/n_t:>6.0f}% {'-':>11} -")

# zero in on the "contact" cases: FLUID DGT/PET == 0 means they overlap physically.
# Our engine should detect those with PET=0.
print("\n[check] FLUID DGT/PET == 0 cases (actual contact / overlap):")
contact = res[res['DGT/PET']==0]
contact_matched = contact.dropna(subset=['our_pet'])
contact_zero = contact_matched[contact_matched['our_pet']==0]
print(f"  total FLUID contact events: {len(contact)}")
print(f"  our engine matched: {len(contact_matched)}")
print(f"  our engine gave PET=0: {len(contact_zero)} / {len(contact_matched)}  ({100*len(contact_zero)/max(len(contact_matched),1):.0f}%)")
