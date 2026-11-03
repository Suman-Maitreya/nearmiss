import pandas as pd
BASE = r"D:\META\nearmiss\data\fluid\derived_FIDRT\derived_data"
fl = pd.read_csv(BASE + r"\flightLog\FIDRT_20250526_video.csv")
print(f"flight log rows: {len(fl):,}")
print(f"time span: {fl['time(millisecond)'].min()} to {fl['time(millisecond)'].max()} ms")
print(f"           ({fl['time(millisecond)'].max()/1000:.1f} seconds)")
print(f"\ncolumns of interest:")
cols_of_interest = ['time(millisecond)', 'height_above_takeoff(feet)', 'altitude_above_seaLevel(feet)', 'speed(mph)',
                    ' compass_heading(degrees)', ' pitch(degrees)', ' roll(degrees)',
                    'gimbal_heading(degrees)', 'gimbal_pitch(degrees)', 'gimbal_roll(degrees)',
                    'flycState']
print(fl[cols_of_interest].head(3).to_string(index=False))

# Also: does the drone move during our event window?
# Our event is at t=375.6s TRAJECTORY time. If flight log starts near 0, that corresponds to log time ~375600 ms
# Convert: find rows near trajectory time 375.6s. We need to find the mapping.
print(f"\nflight log time axis starts at: {fl['time(millisecond)'].iloc[0]} ms")
print(f"flight log time axis ends at:   {fl['time(millisecond)'].iloc[-1]} ms")
print(f"total duration: {(fl['time(millisecond)'].iloc[-1] - fl['time(millisecond)'].iloc[0])/1000:.1f} s")

# Check drone drift over the full session
print(f"\ndrone metadata ranges (over full session):")
for col in ['height_above_takeoff(feet)', ' compass_heading(degrees)', ' pitch(degrees)', ' roll(degrees)',
            'gimbal_pitch(degrees)', 'gimbal_heading(degrees)']:
    if col in fl.columns:
        print(f"  {col:>35}: min={fl[col].min():.2f}  max={fl[col].max():.2f}  range={fl[col].max()-fl[col].min():.2f}")

# Is it in "Tripod" mode throughout? (hovering)
if 'flycState' in fl.columns:
    print(f"\nflycState distribution: {dict(fl['flycState'].value_counts())}")
