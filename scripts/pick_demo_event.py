import pandas as pd
import numpy as np

BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
events = pd.read_csv(r"D:\META\nearmiss\runs\ped_veh_pet_ALL.csv")

print("[A] top 10 critical events (lowest PET first):")
top = events.sort_values(['pet_s','scene']).head(10).reset_index(drop=True)
print(top.to_string(index=False))

print("\n[B] for each of the top 5, pull timing + context from the trajectory:")
for i, row in top.head(5).iterrows():
    scene = row['scene']
    pid = int(row['ped_id'])
    vid = int(row['veh_id'])
    pet = row['pet_s']
    traj = pd.read_csv(BASE + f"\\traj\\{scene}.csv", usecols=['id','time','cx_m','cy_m','type','speed','length_med','width_med','course'])
    p = traj[traj['id']==pid]
    v = traj[traj['id']==vid]
    if len(p)==0 or len(v)==0:
        continue
    # find the time at which they are closest in actual distance
    merged = pd.merge(p[['time','cx_m','cy_m']].rename(columns={'cx_m':'px','cy_m':'py'}),
                      v[['time','cx_m','cy_m','speed']].rename(columns={'cx_m':'vx','cy_m':'vy','speed':'vspeed'}),
                      on='time', how='inner')
    if len(merged)==0:
        print(f"\n  event #{i}: ped {pid} / veh {vid} PET={pet:.2f}s — NO TIME OVERLAP (sequential, not simultaneous)")
        print(f"    ped time:    [{p['time'].min():.1f}, {p['time'].max():.1f}]  pts={len(p)}  type={p['type'].iloc[0]}")
        print(f"    veh time:    [{v['time'].min():.1f}, {v['time'].max():.1f}]  pts={len(v)}  type={v['type'].iloc[0]}  len_med={v['length_med'].median():.1f}m")
        continue
    merged['dist'] = np.sqrt((merged['px']-merged['vx'])**2 + (merged['py']-merged['vy'])**2)
    closest = merged.loc[merged['dist'].idxmin()]
    print(f"\n  event #{i}: scene={scene}  ped {pid} / veh {vid}  PET={pet:.2f}s  type_veh={v['type'].iloc[0]}")
    print(f"    closest observed approach: dist={closest['dist']:.2f}m at t={closest['time']:.1f}s")
    print(f"    ped at that moment: ({closest['px']:.2f}, {closest['py']:.2f})")
    print(f"    veh at that moment: ({closest['vx']:.2f}, {closest['vy']:.2f}) going {closest['vspeed']:.1f} m/s")
    print(f"    ped tracked: [{p['time'].min():.1f}, {p['time'].max():.1f}] s  ({len(p)} pts)")
    print(f"    veh tracked: [{v['time'].min():.1f}, {v['time'].max():.1f}] s  ({len(v)} pts)")
    print(f"    veh dims: len_med={v['length_med'].median():.1f}m  width_med={v['width_med'].median():.1f}m")
