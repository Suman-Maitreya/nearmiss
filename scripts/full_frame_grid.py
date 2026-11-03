import subprocess, os
from PIL import Image, ImageDraw, ImageFont

VIDEO = r"D:\META\nearmiss\data\fluid\videos\20250526_video.mp4"
TMP = r"D:\META\nearmiss\runs\temp_full_frame.jpg"
OUT = r"D:\META\nearmiss\runs\real_frames_ped894_veh871\full_frame_with_grid.jpg"

# Extract one full-size frame at t=375.6
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error",
    "-ss", "375.60", "-i", VIDEO, "-vframes", "1", "-q:v", "2", TMP
], check=True)

im = Image.open(TMP).convert('RGB')
print(f"video frame size: {im.size}")

# The TIF has 25 pixels per metre, world (0,0) at TIF pixel (72.94*25, 47.51*25) = (1824, 1188).
# If the video has the SAME scale, world (0,0) would be at ((W-TIF_width)/2 + 1824, (H-TIF_height)/2 + 1188)
# But the video is 3840x2160 and TIF is 3879x2209, so the video is close but 1% smaller.
# ASSUMPTION: video scale = 25 pix/m * (3840/3879) = 24.75 pix/m
# ASSUMPTION: world (0,0) at video center approx
W, H = im.size
VPIX_PER_M = 25.0 * (W / 3879)  # scale from TIF-size to video-size
CX, CY = W/2, H/2
print(f"guessed scale: {VPIX_PER_M:.3f} pix/m")
print(f"guessed world (0,0) at video pixel ({CX:.0f}, {CY:.0f})")

# Draw crosshairs + a grid in metres
draw = ImageDraw.Draw(im)
try:
    font = ImageFont.truetype("arial.ttf", 36)
except OSError:
    font = ImageFont.load_default()

# Mark where we think world (0, 0) is: red crosshair
draw.line([(CX-40,CY),(CX+40,CY)], fill=(255,0,0), width=4)
draw.line([(CX,CY-40),(CX,CY+40)], fill=(255,0,0), width=4)
draw.text((CX+10, CY-45), "(0,0)?", fill=(255,0,0), font=font, stroke_width=3, stroke_fill=(0,0,0))

# Mark where we think ped 894 at (21.1, 2.3) is: green crosshair
def w2p(x_m, y_m):
    px = CX + x_m * VPIX_PER_M
    py = CY - y_m * VPIX_PER_M  # y flip
    return px, py

px, py = w2p(21.1, 2.3)
draw.line([(px-40,py),(px+40,py)], fill=(0,220,60), width=4)
draw.line([(px,py-40),(px,py+40)], fill=(0,220,60), width=4)
draw.text((px+10, py-45), "P894 guess", fill=(0,220,60), font=font, stroke_width=3, stroke_fill=(0,0,0))

# Mark where we think veh 871 at (19.8, 2.4) is: orange crosshair
vx, vy = w2p(19.8, 2.4)
draw.line([(vx-40,vy),(vx+40,vy)], fill=(255,100,0), width=4)
draw.line([(vx,vy-40),(vx,vy+40)], fill=(255,100,0), width=4)
draw.text((vx+10, vy+30), "V871 guess", fill=(255,100,0), font=font, stroke_width=3, stroke_fill=(0,0,0))

# Grid lines at 10m intervals
GRID_COLOR = (255, 255, 0, 120)
for xm in range(-80, 90, 10):
    gx = CX + xm * VPIX_PER_M
    if 0 <= gx < W:
        draw.line([(gx,0),(gx,H)], fill=GRID_COLOR, width=1)
        draw.text((gx+2, 20), f"x={xm}", fill=(255,255,0), font=font, stroke_width=2, stroke_fill=(0,0,0))

for ym in range(-50, 50, 10):
    gy = CY - ym * VPIX_PER_M
    if 0 <= gy < H:
        draw.line([(0,gy),(W,gy)], fill=GRID_COLOR, width=1)
        draw.text((20, gy+2), f"y={ym}", fill=(255,255,0), font=font, stroke_width=2, stroke_fill=(0,0,0))

im.save(OUT, quality=90)
os.remove(TMP)
print(f"saved: {OUT}")
