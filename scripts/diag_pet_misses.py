import pandas as pd
import numpy as np

BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
traj = pd.read_csv(BASE + r"\traj\20250120_video_Traj.csv")
conf = pd.read_csv(BASE + r"\conflict\FIDRT_conflict.csv")

# look at car 1120 and one of its missed partners
suspect_ids = [1120, 1196, 1482, 1491]
print("[A] trajectory spans of the suspect ids:")
for tid in suspect_ids:
    t = traj[traj['id']==tid].sort_values('time')
    if len(t)==0:
        print(f"  id={tid}: NOT IN TRAJECTORY FILE AT ALL")
        continue
    print(f"  id={tid}: pts={len(t):<5}  time=[{t['time'].min():.1f}..{t['time'].max():.1f}]  type={t['type'].iloc[0]}  cx_m=[{t['cx_m'].min():.1f}..{t['cx_m'].max():.1f}]  cy_m=[{t['cy_m'].min():.1f}..{t['cy_m'].max():.1f}]")

print("\n[B] FLUID conflicts involving car 1120 in session 20250120:")
my = conf[(conf['Scene']=='20250120_video_Traj') & ((conf['Car 1 ID']==1120)|(conf['Car 2 ID']==1120))]
print(my.to_string(index=False))

# For the first conflict row, look at the two cars' positions in a window
print("\n[C] in-window position snapshot for the first 1120-conflict (frame 6317, cars 1120 & 1196):")
# FLUID 'Frame' is video frame; traj uses 'time' (seconds). 10Hz -> frame -> time
# but there's no 'frame' col in traj. Assume time = frame/10 roughly if frame numbers align.
# Instead, find the time at which traj has both cars simultaneously, and show nearest.
row = my.iloc[0]
f = int(row['Frame'])
t_est = f / 10.0  # ASSUMPTION: fluid 'Frame' is at 10Hz
print(f"  FLUID frame={f}  estimated time={t_est}s")
for tid in [1120, 1196]:
    t = traj[(traj['id']==tid) & (traj['time'].between(t_est-1, t_est+1))].sort_values('time')
    print(f"  id={tid}: {len(t)} points in [t-1, t+1]")
    print(t[['time','cx_m','cy_m','type','speed']].head(5).to_string(index=False))

# Also: what fraction of the FLUID conflict Frame values exist as a time in the traj?
print("\n[D] cross-check: do FLUID Frame numbers match traj.time * 10 ?")
# sample 10 conflict pairs for session 20250120
samp = conf[conf['Scene']=='20250120_video_Traj'].sample(10, random_state=0)
for _, r in samp.iterrows():
    f = int(r['Frame'])
    t_est = f/10
    car1 = traj[(traj['id']==int(r['Car 1 ID'])) & (traj['time']==t_est)]
    if len(car1):
        rec_x = car1['cx_m'].iloc[0]
        print(f"  frame {f}, car {int(r['Car 1 ID'])}: declared X={r['Car 1 X']:.2f}  traj X at t={t_est}: {rec_x:.2f}  match={abs(rec_x-r['Car 1 X'])<0.1}")
    else:
        print(f"  frame {f}, car {int(r['Car 1 ID'])}: no traj row at exact t={t_est}s")
