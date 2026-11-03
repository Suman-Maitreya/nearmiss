import subprocess
VIDEO = r"D:\META\nearmiss\data\fluid\videos\20250526_video.mp4"
# At frame 3 (t=375.6s), extract and crop a 1200x1200 region around the center-right
# of the 4K image where our (21, 2)m point should be
out = r"D:\META\nearmiss\runs\real_frames_ped894_veh871\crop_t0.jpg"
# Try the center-right quadrant first; we will refine after seeing it
cmd = [
    "ffmpeg", "-y", "-loglevel", "error",
    "-ss", "375.60",
    "-i", VIDEO,
    "-vframes", "1",
    "-vf", "crop=1600:1600:1600:400",  # x=1600 (right of center), y=400 (upper-mid)
    "-q:v", "2",
    out
]
r = subprocess.run(cmd, capture_output=True, text=True)
print("return:", r.returncode)
if r.returncode != 0:
    print(r.stderr)
else:
    print(f"saved to {out}")
