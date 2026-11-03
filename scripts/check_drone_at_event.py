import pandas as pd
BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
fl = pd.read_csv(BASE + r"\flightLog\FIDRT_20250526_video.csv", low_memory=False)
traj = pd.read_csv(BASE + r"\traj\20250526_video_Traj.csv", usecols=['time'])

print(f"[A] trajectory time axis: [{traj['time'].min():.1f}, {traj['time'].max():.1f}] s")
print(f"    flight log time axis: [{fl['time(millisecond)'].min()/1000:.1f}, {fl['time(millisecond)'].max()/1000:.1f}] s")

# If both axes represent wall-clock time, their spans should match
# Trajectory span:
traj_span = traj['time'].max() - traj['time'].min()
fl_span = (fl['time(millisecond)'].max() - fl['time(millisecond)'].min()) / 1000
print(f"    trajectory span: {traj_span:.1f}s")
print(f"    flight log span: {fl_span:.1f}s  (longer than traj by {fl_span-traj_span:.1f}s — includes takeoff/landing)")

# Hypothesis: both share a wall-clock origin. Flight log starts at 284.5s (drone powered on then).
# Trajectory starts at t=traj.min(), which is probably 0.
# Try two hypotheses and see which puts drone in Tripod mode during the recording
print(f"\n[B] drone state during our event (trajectory t=375.6s)")

# Hypothesis 1: trajectory_s + 284.5 = flight_log_s
# (i.e. trajectory time 0 = flight log time 284.5s = when video recording started)
flight_t_h1 = 375.6 + 284.5
print(f"    H1: traj_t=375.6s -> flight_log_t={flight_t_h1}s = {flight_t_h1*1000:.0f}ms")

# Find flight log row nearest that time
near_h1 = fl.iloc[(fl['time(millisecond)'] - flight_t_h1*1000).abs().argsort()[:5]]
print(f"    nearest 5 flight log rows (H1):")
cols = ['time(millisecond)','height_above_takeoff(feet)','speed(mph)',
        ' compass_heading(degrees)','gimbal_heading(degrees)','gimbal_pitch(degrees)','flycState']
print(near_h1[cols].to_string(index=False))

# Also check what the drone was doing across a 30s window around our event (H1)
print(f"\n[C] drone state in 30s window around event (H1)")
window = fl[(fl['time(millisecond)'] >= (flight_t_h1-15)*1000) &
            (fl['time(millisecond)'] <= (flight_t_h1+15)*1000)]
print(f"    {len(window)} rows in window")
print(f"    flycState: {dict(window['flycState'].value_counts())}")
print(f"    height_above_takeoff: {window['height_above_takeoff(feet)'].min():.2f} to {window['height_above_takeoff(feet)'].max():.2f} ft  (range {window['height_above_takeoff(feet)'].max()-window['height_above_takeoff(feet)'].min():.2f} ft)")
print(f"    speed(mph): max={window['speed(mph)'].max():.2f}")
print(f"    compass_heading: {window[' compass_heading(degrees)'].min():.2f} to {window[' compass_heading(degrees)'].max():.2f} deg")
print(f"    gimbal_heading: {window['gimbal_heading(degrees)'].min():.2f} to {window['gimbal_heading(degrees)'].max():.2f} deg")
print(f"    gimbal_pitch: {window['gimbal_pitch(degrees)'].min():.2f} to {window['gimbal_pitch(degrees)'].max():.2f} deg")
