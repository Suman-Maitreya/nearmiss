# NearMiss — FLUID Dataset Findings

Inspected 2026-11-03. Source: FLUID FIDRT (Figshare 10.6084/m9.figshare.29974954).

## Package contents

- `derived_FIDRT/derived_data/traj/*.csv` — per-session trajectory, 3 sessions
  (20250120, 20250525, 20250526). Columns include cx_m, cy_m, time, type,
  speed, vx, vy — metric coordinates with drone-motion already corrected.
- `derived_FIDRT/derived_data/conflict/FIDRT_conflict.csv` — **147 labelled
  conflict events** with vehicle IDs, metric (X,Y), TTC, MTTC, PET,
  conflict_type. VEHICLE-VEHICLE only.
- `derived_FIDRT/derived_data/signal/*_signal.csv` — traffic-signal phases per
  session, with direction/turn/begin_time/end_time/state (G/r).
- `derived_FIDRT/derived_data/flightLog/*_video.csv` — DJI drone flight log,
  one row per 100ms, position/attitude/battery. Shows drone hovers in
  "Tripod" state but can drift.
- `derived_FIDRT/derived_data/route/*_Route.csv` — per-session route data
  (large files, not yet inspected).
- `derived_FIDRT/derived_data/map/FIDRT.osm` — OSM in LOCAL frame
  (lat/lon values near 0; origin is the intersection centre, metres approx.
  lat*111_000 and lon*cos(lat)*111_000).
- `derived_FIDRT/derived_data/map/FIDRT.tif` + `FIDRT_wgs84.tif` —
  georeferenced raster of the intersection. CRS is in the TIF header.

## Coordinate system (critical)

- `cx_m, cy_m` in traj CSVs are METRES in a local projected frame.
- The frame's origin is the intersection centre.
- The frame is drone-motion-corrected: a stationary ground point has a
  constant (cx_m, cy_m) across all frames even when the drone drifts.
- Pixel coordinates (cx, cy) are per-frame drone-view pixels. Their mapping
  to metres is NOT a single global homography — it changes per frame as the
  drone drifts.

## Calibration gate (Architecture 2.1 §16 Step 5)

We do NOT need to derive a homography. FLUID publishes `cx_m, cy_m` in a
documented metric frame already. Our validator must only CONFIRM that:

1. `cx_m, cy_m` units are metres and consistent across sessions
2. Metric distances between stationary ground features match map (±0.5 m)
3. Vehicle speeds in `speed` column match time-derivative of (cx_m, cy_m)

If all three pass, FLUID calibration is accepted for Phase 2 PET.

## PET validation (Architecture 2.1 §16 Step 6)

`FIDRT_conflict.csv` is published PET ground truth for 147 vehicle-vehicle
events. Our grid-PET output can be scored directly against the `DGT/PET`
column for the same (Scene, Car 1 ID, Car 2 ID) pairs.

This gives us a credible evaluation story: "On FLUID, our PET agrees with
the published values within X seconds on 147 real conflicts."

Vehicle-pedestrian conflicts are NOT in `conflict.csv`. For those we have to
run our own detection on the trajectory file and treat FLUID's trajectories
as ground truth (position + type), not the conflicts themselves.

## Scope note

FLUID is a Chinese drone dataset — the camera is NOT a fixed CCTV, so the
"fixed-camera, oblique" view mode of Architecture 2.1 §6.4 does not apply
literally here. FLUID is treated as "topdown with drone-corrected metric
frame", which is a different (and easier) class of input for physics work.
TAD stays our "fixed-camera, no metric time" clip for perception + Spark
visual review only.
