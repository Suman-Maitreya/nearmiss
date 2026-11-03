"""Phase 3 decision: combine deterministic PET with Spark's neutral review.

Spark does NOT see PET or severity. We decide status here.
"""
import json, os, sys

EVENT_DIR = r"D:\META\nearmiss\runs\evidence_event_ped894_veh871"

with open(os.path.join(EVENT_DIR, "spark_review.json")) as f:
    review = json.load(f)
with open(os.path.join(EVENT_DIR, "metadata.json")) as f:
    meta = json.load(f)

pet = meta["our_pet_s"]
severity = meta["severity"]
spark = review["spark_response"]

ped_ok = spark.get("pedestrian_on_crossing") == "yes"
veh_ok = spark.get("vehicle_on_road")       == "yes"
paths  = spark.get("paths_close")
closest = spark.get("closest_frame")

# Deterministic decision table
flags = []
if not ped_ok: flags.append("spark_doubts_pedestrian")
if not veh_ok: flags.append("spark_doubts_vehicle_overlay")

if paths == "no":
    status = "rejected"
    status_reason = "Spark reports pedestrian and vehicle paths do not come close"
elif paths == "unsure":
    status = "unclear"
    status_reason = "Spark unsure whether paths come close; sent to human review queue"
elif paths == "yes":
    if flags:
        status = "supported_with_flag"
        status_reason = f"Spatial-temporal overlap confirmed by Spark, but visual flags: {', '.join(flags)}"
    else:
        status = "supported"
        status_reason = "Spark confirms pedestrian on crossing, vehicle on road, and paths close"
else:
    status = "unverified"
    status_reason = f"Spark returned unexpected paths_close value: {paths}"

# Also sanity: does Spark's closest_frame agree with physics? (frame 3 == t=0.0s == physics conflict moment)
closest_frame_matches = (closest == 3)

event_record = {
    "event_id": f"{meta['scene']}_ped{meta['ped_id']}_veh{meta['veh_id']}",
    "scene": meta["scene"],
    "ped_id": meta["ped_id"],
    "veh_id": meta["veh_id"],
    "conflict_time_s": meta["conflict_time_s"],
    "closest_approach_m": meta["closest_approach_m"],
    "our_pet_s": pet,
    "severity": severity,
    "spark_review": spark,
    "closest_frame_matches_physics": closest_frame_matches,
    "status": status,
    "status_reason": status_reason,
    "flags": flags,
    "needs_human_review": status in ("supported_with_flag", "unclear"),
    "evidence_dir": EVENT_DIR,
    "evidence_frames": [f"frame_{i:02d}_t{off:+.1f}s.jpg" for i, off in enumerate([-3.0,-2.0,-1.0,0.0,1.0,2.0,3.0])],
}

OUT = os.path.join(EVENT_DIR, "event_record.json")
with open(OUT, "w") as f:
    json.dump(event_record, f, indent=2)

print(f"EVENT RECORD")
print("="*60)
print(f"  Event: {event_record['event_id']}")
print(f"  Our PET:              {pet}s ({severity})")
print(f"  Spark closest frame:  {closest} (physics expects 3)  match={closest_frame_matches}")
print(f"  Spark ped on crossing: {spark['pedestrian_on_crossing']}")
print(f"  Spark veh on road:    {spark['vehicle_on_road']}")
print(f"  Spark paths close:    {spark['paths_close']}")
print()
print(f"  STATUS: {status.upper()}")
print(f"  Reason: {status_reason}")
print(f"  Flags:  {flags or '(none)'}")
print(f"  Needs human review: {event_record['needs_human_review']}")
print()
print(f"  Saved: {OUT}")
