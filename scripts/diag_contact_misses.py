import pandas as pd
import numpy as np

BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
conf = pd.read_csv(BASE + r"\conflict\FIDRT_conflict.csv")

# contact events (DGT/PET == 0) we missed
scene = '20250120_video_Traj'
traj = pd.read_csv(BASE + f"\\traj\\{scene}.csv")

contacts = conf[(conf['Scene']==scene) & (conf['DGT/PET']==0)].reset_index(drop=True)
print(f"[A] {len(contacts)} contact events in session 20250120")

# For each of first 5 contact events, show closest approach we actually observe
for idx, row in contacts.head(5).iterrows():
    f = int(row['Frame'])
    t_c = f / 10.0
    c1, c2 = int(row['Car 1 ID']), int(row['Car 2 ID'])
    print(f"\n=== event #{idx}: frame {f} (t={t_c}s), cars {c1} & {c2}, type={row['conflict_type']} ===")
    print(f"    FLUID declares: car1@({row['Car 1 X']:.2f},{row['Car 1 Y']:.2f}), car2@({row['Car 2 X']:.2f},{row['Car 2 Y']:.2f}), diff={row['diff']:.2f}m, DGT/PET={row['DGT/PET']:.1f}")

    # positions of both cars in window t_c-2 .. t_c+2
    t1 = traj[(traj['id']==c1) & (traj['time'].between(t_c-2, t_c+2))].sort_values('time').reset_index(drop=True)
    t2 = traj[(traj['id']==c2) & (traj['time'].between(t_c-2, t_c+2))].sort_values('time').reset_index(drop=True)
    print(f"    car1 pts in window: {len(t1)}   car2 pts in window: {len(t2)}")
    if len(t1)==0 or len(t2)==0:
        continue

    # for every pair of (t1 row, t2 row) at the SAME time, compute distance
    merged = pd.merge(t1[['time','cx_m','cy_m','type']].rename(columns={'cx_m':'x1','cy_m':'y1','type':'type1'}),
                      t2[['time','cx_m','cy_m','type']].rename(columns={'cx_m':'x2','cy_m':'y2','type':'type2'}),
                      on='time', how='inner')
    merged['dist'] = np.sqrt((merged['x1']-merged['x2'])**2 + (merged['y1']-merged['y2'])**2)
    print(f"    common-timestamp rows: {len(merged)}")
    if len(merged):
        min_row = merged.loc[merged['dist'].idxmin()]
        print(f"    closest observed approach: dist={min_row['dist']:.2f}m at t={min_row['time']:.1f}s")
        print(f"      car1=({min_row['x1']:.2f},{min_row['y1']:.2f}) type={min_row['type1']}")
        print(f"      car2=({min_row['x2']:.2f},{min_row['y2']:.2f}) type={min_row['type2']}")

        # also: did either car visit the OTHER's location at ANY time?
        c1_cells = set((int(x/0.5), int(y/0.5)) for x,y in zip(traj[traj['id']==c1]['cx_m'], traj[traj['id']==c1]['cy_m']))
        c2_cells = set((int(x/0.5), int(y/0.5)) for x,y in zip(traj[traj['id']==c2]['cx_m'], traj[traj['id']==c2]['cy_m']))
        shared = c1_cells & c2_cells
        print(f"    shared cells across ENTIRE track (no time window): {len(shared)}")
