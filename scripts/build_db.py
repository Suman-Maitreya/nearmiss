"""Create nearmiss.db schema and populate from existing run files.

Architecture 2.1 §11: single SQLite DB.
"""
import sqlite3, pandas as pd, json, os, datetime

DB = r"D:\META\nearmiss\nearmiss.db"
EVENTS_CSV = r"D:\META\nearmiss\runs\ped_veh_pet_ALL.csv"
REVIEWED_EVENT_DIR = r"D:\META\nearmiss\runs\real_evidence_ped894_veh871"

con = sqlite3.connect(DB)
cur = con.cursor()

cur.executescript("""
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS coverage;

CREATE TABLE events (
    event_id              TEXT PRIMARY KEY,
    scene                 TEXT NOT NULL,
    ped_id                INTEGER NOT NULL,
    veh_id                INTEGER NOT NULL,
    conflict_time_s       REAL,
    closest_approach_m    REAL,
    our_pet_s             REAL NOT NULL,
    severity              TEXT NOT NULL,
    spark_status          TEXT DEFAULT 'not_yet_reviewed',
    spark_flags           TEXT,
    spark_observation     TEXT,
    needs_human_review    INTEGER DEFAULT 0,
    human_review_status   TEXT DEFAULT 'pending',
    human_review_note     TEXT,
    evidence_dir          TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);

CREATE INDEX idx_events_scene ON events(scene);
CREATE INDEX idx_events_severity ON events(severity);
CREATE INDEX idx_events_needs_review ON events(needs_human_review);

CREATE TABLE coverage (
    scene                 TEXT PRIMARY KEY,
    time_start_s          REAL,
    time_end_s            REAL,
    duration_s            REAL,
    ped_count             INTEGER,
    veh_count             INTEGER,
    candidate_pair_count  INTEGER,
    event_count           INTEGER,
    critical_count        INTEGER,
    serious_count         INTEGER,
    moderate_count        INTEGER,
    median_pet_s          REAL,
    min_pet_s             REAL,
    processed_at          TEXT NOT NULL
);
""")
con.commit()
print("[1/4] schema created")

events = pd.read_csv(EVENTS_CSV)

def severity_of(p):
    if p <= 1.0: return 'critical'
    if p <= 1.5: return 'serious'
    return 'moderate'

now = datetime.datetime.utcnow().isoformat()
rows = []
for _, r in events.iterrows():
    ev_id = f"{r['scene']}_ped{int(r['ped_id'])}_veh{int(r['veh_id'])}"
    rows.append((
        ev_id, r['scene'], int(r['ped_id']), int(r['veh_id']),
        None, None,
        float(r['pet_s']), severity_of(r['pet_s']),
        'not_yet_reviewed', None, None, 0, 'pending', None, None,
        now, now
    ))
cur.executemany("""
INSERT INTO events (event_id, scene, ped_id, veh_id, conflict_time_s,
    closest_approach_m, our_pet_s, severity, spark_status, spark_flags,
    spark_observation, needs_human_review, human_review_status,
    human_review_note, evidence_dir, created_at, updated_at)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
""", rows)
con.commit()
print(f"[2/4] inserted {len(rows)} events")

with open(os.path.join(REVIEWED_EVENT_DIR, "event_record.json")) as f:
    rev = json.load(f)
ev_id = rev['event_id']
cur.execute("""
UPDATE events SET
    conflict_time_s = ?,
    closest_approach_m = ?,
    spark_status = ?,
    spark_flags = ?,
    spark_observation = ?,
    needs_human_review = ?,
    evidence_dir = ?,
    updated_at = ?
WHERE event_id = ?
""", (
    rev['conflict_time_s'], rev['closest_approach_m'],
    rev['status'], json.dumps(rev['flags']),
    rev['spark_review']['observation'],
    1 if rev['needs_human_review'] else 0,
    rev['evidence_dir'], now, ev_id
))
con.commit()
print(f"[3/4] patched reviewed event: {ev_id}")

sessions = events.groupby('scene').agg(
    event_count=('pet_s','count'),
    median_pet=('pet_s','median'),
    min_pet=('pet_s','min'),
).reset_index()

known_per_scene = {
    '20250120_video_Traj': dict(duration=1270.8, peds=76, vehs=1115, candidates=589),
    '20250525_video_Traj': dict(duration=None,   peds=42, vehs=347,  candidates=246),
    '20250526_video_Traj': dict(duration=1729.2, peds=322,vehs=922,  candidates=1080),
}

for _, r in sessions.iterrows():
    scene = r['scene']
    sub = events[events['scene']==scene]
    crit = (sub['pet_s']<=1.0).sum()
    ser  = ((sub['pet_s']>1.0)&(sub['pet_s']<=1.5)).sum()
    mod  = ((sub['pet_s']>1.5)&(sub['pet_s']<=2.0)).sum()
    k = known_per_scene.get(scene, {})
    cur.execute("""
    INSERT INTO coverage (scene, time_start_s, time_end_s, duration_s,
        ped_count, veh_count, candidate_pair_count, event_count,
        critical_count, serious_count, moderate_count,
        median_pet_s, min_pet_s, processed_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        scene, 0.0, k.get('duration'), k.get('duration'),
        k.get('peds'), k.get('vehs'), k.get('candidates'),
        int(r['event_count']), int(crit), int(ser), int(mod),
        float(r['median_pet']), float(r['min_pet']), now
    ))
con.commit()
print(f"[4/4] inserted {len(sessions)} coverage rows")

print()
print("="*60)
print("DATABASE SUMMARY")
print("="*60)
for row in cur.execute("SELECT scene, event_count, critical_count, serious_count, moderate_count, median_pet_s, min_pet_s FROM coverage"):
    print(f"  {row[0]}: events={row[1]}  crit={row[2]}  ser={row[3]}  mod={row[4]}  median={row[5]:.2f}s  min={row[6]:.2f}s")

total      = cur.execute("SELECT COUNT(*) FROM events").fetchone()[0]
crit_total = cur.execute("SELECT COUNT(*) FROM events WHERE severity = 'critical'").fetchone()[0]
need_rev   = cur.execute("SELECT COUNT(*) FROM events WHERE needs_human_review = 1").fetchone()[0]
reviewed   = cur.execute("SELECT COUNT(*) FROM events WHERE spark_status != 'not_yet_reviewed'").fetchone()[0]

print()
print(f"Total events:     {total}")
print(f"Critical events:  {crit_total}")
print(f"Needs human review: {need_rev}")
print(f"Spark reviewed:   {reviewed}")
print()
print(f"Database: {DB}")
con.close()
