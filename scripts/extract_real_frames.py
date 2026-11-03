import os, subprocess
VIDEO = r"D:\META\nearmiss\data\fluid\videos\20250526_video.mp4"
OUT_DIR = r"D:\META\nearmiss\runs\real_frames_ped894_veh871"
os.makedirs(OUT_DIR, exist_ok=True)

T_CONFLICT = 375.6
FPS = 10
offsets = [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0]

for i, off in enumerate(offsets):
    t = T_CONFLICT + off
    out_path = os.path.join(OUT_DIR, f"raw_{i:02d}_t{off:+.1f}s.jpg")
    # -ss before -i for fast seek, then -vframes 1 for exactly one frame.
    # Use -accurate_seek via -ss AFTER -i for precision.
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{t:.3f}",
        "-i", VIDEO,
        "-vframes", "1",
        "-q:v", "2",
        out_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        size = os.path.getsize(out_path)//1024
        print(f"  frame {i} (t={off:+.1f}s, abs={t:.2f}s): saved ({size} KB)")
    else:
        print(f"  frame {i} FAILED:")
        print(r.stderr)
print(f"\noutput folder: {OUT_DIR}")
