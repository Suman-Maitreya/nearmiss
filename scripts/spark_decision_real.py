"""Phase 3 decision applied to real-video Spark review."""
import json, os

EVENT_DIR = r"D:\META\nearmiss\runs\real_evidence_ped894_veh871"
with open(os.path.join(EVENT_DIR, "spark_review.json")) as f:
    review = json.load(f)
with open(os.path.join(EVENT_DIR, "metadata.json")) as f:
    meta = json.load(f)

pet = meta["our_pet_s"]
severity = meta["severity"]
spark = review["spark_response"]

ped_ok = spark.get("pedestrian_overlay_on_real_pedestrian") == "yes"
veh_ok = spark.get("vehicle_overlay_on_real_vehicle") == "yes"
paths = spark.get("paths_close")
closest = spark.get("closest_frame")

flags = []
if spark.get("pedestrian_overlay_on_real_pedestrian") == "unsure":
    flags.append("ped_visibility_marginal_at_4K")
if not veh_ok:
    flags.append("spark_doubts_vehicle_overlay")

if paths == "no":
    status = "rejected"
    reason = "Spark reports paths do not come close"
elif paths == "unsure":
    status = "unclear"
    reason = "Spark unsure whether paths come close; queued for human review"
elif paths == "yes" and veh_ok:
    if flags:
        status = "supported_with_flag"
        reason = f"Vehicle track confirmed, paths close confirmed; flags: {', '.join(flags)}"
    else:
        status = "supported"
        reason = "Spark confirms pedestrian, vehicle, and close paths"
elif paths == "yes" and not veh_ok:
    status = "supported_with_flag"
    reason = f"Paths close but vehicle overlay disputed; flags: {', '.join(flags)}"
else:
    status = "unverified"
    reason = f"unexpected Spark output; paths_close={paths}"

event_record = {
    "event_id": f"{meta['scene']}_ped{meta['ped_id']}_veh{meta['veh_id']}",
    "scene": meta["scene"],
    "ped_id": meta["ped_id"],
    "veh_id": meta["veh_id"],
    "conflict_time_s": meta["conflict_time_s"],
    "closest_approach_m": meta["closest_approach_m"],
    "our_pet_s": pet,
    "severity": severity,
    "render_mode": meta.get("render_mode"),
    "spark_review": spark,
    "closest_frame_matches_physics": (closest == 3),
    "status": status,
    "status_reason": reason,
    "flags": flags,
    "needs_human_review": status in ("supported_with_flag", "unclear"),
    "evidence_dir": EVENT_DIR,
    "evidence_frames": [f"frame_{i:02d}_t{off:+.1f}s.jpg" for i, off in enumerate([-3.0,-2.0,-1.0,0.0,1.0,2.0,3.0])],
}

OUT = os.path.join(EVENT_DIR, "event_record.json")
with open(OUT, "w") as f:
    json.dump(event_record, f, indent=2)

print("EVENT RECORD (real-video evidence)")
print("="*60)
print(f"  Event: {event_record['event_id']}")
print(f"  Physics: PET = {pet}s ({severity}), closest approach {meta['closest_approach_m']:.2f} m")
print()
print(f"  Spark closest frame: {closest} (physics expects 3) match={event_record['closest_frame_matches_physics']}")
print(f"  Spark ped_overlay:   {spark['pedestrian_overlay_on_real_pedestrian']}")
print(f"  Spark veh_overlay:   {spark['vehicle_overlay_on_real_vehicle']}")
print(f"  Spark paths_close:   {spark['paths_close']}")
print(f"  Spark observation:   {spark['observation'][:150]}...")
print()
print(f"  STATUS: {status.upper()}")
print(f"  Reason: {reason}")
print(f"  Flags:  {flags or '(none)'}")
print(f"  Needs human review: {event_record['needs_human_review']}")
print()
print(f"  Saved -> {OUT}")
