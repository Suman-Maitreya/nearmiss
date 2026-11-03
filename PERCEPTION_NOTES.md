# NearMiss — SAM 3.1 Perception Notes

Findings from the §16 Step 4 go/no-go test on 2026-11-03.
Golden clip: tad_abnormal_01_Accident_022 (720x406, 911 frames).

## Status: PASS at ladder level L1 (hosted SAM video)
No fallback (L2 image+ByteTrack / L3 self-host / L4 YOLO) needed for this clip.

## Verified behaviour

| Concept | Clip window | Frames covered | Boxes | Notes |
|---|---|---|---|---|
| `car`    | first 300  | 300/300 | 1636 | ~5.5 cars per frame average |
| `person` | f600..909  | 310/310 | 827  | ~2.7 people per frame average |

Latency: ~15-20s per 300 frames + ~5s upload. Scaling: ~45-60s per concept per 900-frame clip.
Stream size: car=996 KB, person=332 KB (for 300-frame windows).

## Concept phrasing — IMPORTANT

SAM 3.1 expects VISUAL noun phrases, not semantic category labels.

- `person`     -> works (310/310 frames)
- `pedestrian` -> returns an empty response (0/300 frames) — SAM does not treat this as a visual concept

Config `sam.prompts` must use visual nouns only. Our list is already correct:
  [person, motorcycle, scooter, "auto rickshaw", car, bus, truck]

Downstream code must map `person` -> role=`pedestrian` for conflict/PET logic
(the user-facing word for someone on foot stays `pedestrian`).

## Streaming event pattern

The OpenAI Python SDK `responses.stream()` for sam-3.1 does NOT fire
`response.output_text.delta` events with populated `.delta` strings.
Instead, the full stream text arrives in the final response:

    with client.responses.stream(model="sam-3.1", input=[...]) as stream:
        for event in stream:
            pass   # events fire but deltas are empty strings
        final = stream.get_final_response()
    raw = final.output[0].content[0].text

Phase 1 code should read from the final response, not accumulate deltas.
(Still iterate events so the stream drives to completion.)

## Response format

Each frame marker is `<Nf>`, then comma-separated per-object entries:
  ordinal `<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..|><|mask;x=..;y=..;data=..|>`
w/h on every box are the frame dimensions, not the box size. Mask uses
`~` prefix for lossless, `!` for 1-bit. Parse with `meta-sam-parser`.

Box coords are clamped to video dims (720x406). Our 1px bottom pad added
during reconstruction does not shift any coordinate we care about.

## What is still untested on L1

- One request per concept — we have NOT yet confirmed that passing multiple
  concepts in one request is supported. The docs say "one concept per
  request". Our pipeline runs 7 concepts, so plan on 7 requests per clip.
- 16-object-per-frame saturation. We have not yet seen saturation on this
  clip (cars peaked at ~6/frame, people at ~3/frame). Need a busy-scene clip
  (e.g. a FLUID crosswalk during peak) to exercise the saturation branch.
- Confidence scores (`metadata.include_confidence=true`) not yet tested.
- Billing — a 300-frame request charged against credits. Watch the running
  total after the full 7-concept run.
