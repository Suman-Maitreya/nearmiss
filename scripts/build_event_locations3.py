import sqlite3
import pandas as pd
import numpy as np
import os

DB = "/tmp/nmwork/nearmiss.db"
TRAJ_DIR = os.path.expanduser("~/mnt/nearmiss/data/fluid/derived_FIDRT/derived_data/traj")

SCENE_TO_CSV = {
    "20250120_video_Traj": "20250120_video_Traj.csv",
    "20250525_video_Traj": "20250525_video_Traj.csv",
    "20250526_video_Traj": "20250526_video_Traj.csv",
}

con = sqlite3.connect(DB)
cur = con.cursor()

existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(events)").fetchall()}
for col, typ in [("loc_x_m", "REAL"), ("loc_y_m", "REAL"), ("vehicle_type", "TEXT"), ("computed_closest_time_s", "REAL")]:
    if col not in existing_cols:
        cur.execute(f"ALTER TABLE events ADD COLUMN {col} {typ}")
con.commit()

events = pd.read_sql_query(
    "SELECT event_id, scene, ped_id, veh_id, conflict_time_s, closest_approach_m FROM events", con
)

traj_cache = {}
def load_traj(scene):
    if scene not in traj_cache:
        path = os.path.join(TRAJ_DIR, SCENE_TO_CSV[scene])
        df = pd.read_csv(path, usecols=["id", "time", "cx_m", "cy_m", "type"])
        traj_cache[scene] = df
    return traj_cache[scene]

updates = []
sanity_diffs = []
missing = 0

for _, row in events.iterrows():
    df = load_traj(row["scene"])
    ped = df[df["id"] == row["ped_id"]][["time", "cx_m", "cy_m"]].rename(columns={"cx_m": "px", "cy_m": "py"})
    veh = df[df["id"] == row["veh_id"]][["time", "cx_m", "cy_m"]]
    vtype_rows = df[df["id"] == row["veh_id"]]["type"].mode()
    vtype = vtype_rows.iloc[0] if not vtype_rows.empty else None

    if ped.empty or veh.empty:
        missing += 1
        continue

    # merge on nearest time within overlap, then find true closest-approach frame
    merged = pd.merge_asof(
        ped.sort_values("time"), veh.sort_values("time").rename(columns={"cx_m": "vx", "cy_m": "vy"}),
        on="time", direction="nearest", tolerance=0.5,
    )
    merged = merged.dropna(subset=["vx", "vy"])
    if merged.empty:
        missing += 1
        continue

    merged["dist"] = np.hypot(merged["px"] - merged["vx"], merged["py"] - merged["vy"])
    closest = merged.loc[merged["dist"].idxmin()]

    loc_x = (closest["px"] + closest["vx"]) / 2.0
    loc_y = (closest["py"] + closest["vy"]) / 2.0

    updates.append((float(loc_x), float(loc_y), vtype, float(closest["time"]), row["event_id"]))

    if pd.notna(row["closest_approach_m"]):
        sanity_diffs.append(abs(closest["dist"] - row["closest_approach_m"]))

cur.executemany(
    "UPDATE events SET loc_x_m=?, loc_y_m=?, vehicle_type=?, computed_closest_time_s=? WHERE event_id=?",
    updates,
)
con.commit()

print(f"Updated {len(updates)} / {len(events)} events; {missing} could not be located.")
if sanity_diffs:
    sd = pd.Series(sanity_diffs)
    print("sanity check vs stored closest_approach_m -> mean abs diff:", sd.mean(), "max diff:", sd.max())

df_after = pd.read_sql_query("SELECT vehicle_type, severity FROM events", con)
print(df_after["vehicle_type"].value_counts(dropna=False))
print(pd.crosstab(df_after["vehicle_type"], df_after["severity"]))
con.close()
