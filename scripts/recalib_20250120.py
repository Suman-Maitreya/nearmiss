import subprocess, os
from PIL import Image, ImageDraw, ImageFont

VIDEO = r"D:\META\nearmiss\data\fluid\videos\20250120_video.mp4"
OUT = r"D:\META\nearmiss\runs\calib_20250120_v2.jpg"
PIX_PER_M = 22.94  # corrected scale for this session

try:
    font = ImageFont.truetype("arial.ttf", 36)
except OSError:
    font = ImageFont.load_default()

tmp = OUT + ".tmp.jpg"
subprocess.run(["ffmpeg","-y","-loglevel","error","-ss","400","-i",VIDEO,"-vframes","1","-q:v","2",tmp], check=True)
im = Image.open(tmp).convert('RGB')
W, H = im.size
CX, CY = W/2, H/2
draw = ImageDraw.Draw(im)

for xm in range(-80, 90, 10):
    gx = CX + xm * PIX_PER_M
    if 0 <= gx < W:
        draw.line([(gx, 0), (gx, H)], fill=(255,255,0), width=1)
        draw.text((gx+2, 20), f"x={xm}", fill=(255,255,0), font=font, stroke_width=2, stroke_fill=(0,0,0))
for ym in range(-50, 50, 10):
    gy = CY - ym * PIX_PER_M
    if 0 <= gy < H:
        draw.line([(0, gy), (W, gy)], fill=(255,255,0), width=1)
        draw.text((20, gy+2), f"y={ym}", fill=(255,255,0), font=font, stroke_width=2, stroke_fill=(0,0,0))

r = 80
draw.line([(CX-r, CY), (CX+r, CY)], fill=(255,0,0), width=6)
draw.line([(CX, CY-r), (CX, CY+r)], fill=(255,0,0), width=6)
draw.rectangle([(CX+15, CY-55), (CX+280, CY-15)], fill=(0,0,0,220))
draw.text((CX+22, CY-48), "(0,0) corrected 22.94", fill=(80,255,80), font=font)

im.save(OUT, quality=85)
os.remove(tmp)
print(f"saved: {OUT}")
