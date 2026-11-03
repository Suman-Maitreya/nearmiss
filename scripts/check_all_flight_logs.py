import pandas as pd
BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data\flightLog"

# Session 20250526 at t=375.6s (our calibrated reference)
# We know: drone was in Tripod, altitude 393 ft, compass 359.8-359.9, gimbal pitch -90

sessions = {
    '20250120': [100.0, 400.0, 800.0, 1100.0],
    '20250525': [50.0, 150.0, 250.0, 350.0],
    '20250526': [375.6, 500.0, 1000.0, 1500.0],
}

for sess, times in sessions.items():
    fl = pd.read_csv(f"{BASE}\\FIDRT_{sess}_video.csv", low_memory=False)
    log_start_ms = fl['time(millisecond)'].min()
    print(f"\n=== session {sess} ===")
    print(f"  log starts at: {log_start_ms} ms ({log_start_ms/1000:.1f} s)")
    for t_rep in times:
        target_ms = log_start_ms + t_rep * 1000
        nearest = fl.iloc[(fl['time(millisecond)'] - target_ms).abs().argsort()[:1]]
        n = nearest.iloc[0]
        print(f"  @ video t={t_rep:6.1f}s: alt={n['height_above_takeoff(feet)']:.1f}ft  compass={n[' compass_heading(degrees)']:.1f}  gimbal_h={n['gimbal_heading(degrees)']:.1f}  gimbal_pitch={n['gimbal_pitch(degrees)']:.1f}  state={n['flycState']}")

    # Summary across whole session
    print(f"  SESSION SUMMARY:")
    print(f"    altitude range: {fl['height_above_takeoff(feet)'].min():.1f} to {fl['height_above_takeoff(feet)'].max():.1f} ft")
    print(f"    heading range: {fl[' compass_heading(degrees)'].min():.1f} to {fl[' compass_heading(degrees)'].max():.1f}")
    print(f"    gimbal pitch range: {fl['gimbal_pitch(degrees)'].min():.1f} to {fl['gimbal_pitch(degrees)'].max():.1f}")
    print(f"    Tripod rows: {(fl['flycState']=='Tripod').sum()} / {len(fl)}")
