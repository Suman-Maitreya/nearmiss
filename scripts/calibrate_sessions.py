import subprocess, os
from PIL import Image, ImageDraw, ImageFont

PIX_PER_M = 24.75

try:
    font = ImageFont.truetype("arial.ttf", 36)
except OSError:
    font = ImageFont.load_default()

def grid_overlay(video, out_path, sample_time_s):
    tmp = out_path + ".tmp.jpg"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-ss",f"{sample_time_s:.1f}","-i",video,"-vframes","1","-q:v","2",tmp], check=True)
    im = Image.open(tmp).convert('RGB')
    W, H = im.size
    CX, CY = W/2, H/2

    draw = ImageDraw.Draw(im)
    # yellow grid every 10m
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

    # red cross at assumed world (0,0)
    r = 80
    draw.line([(CX-r, CY), (CX+r, CY)], fill=(255,0,0), width=6)
    draw.line([(CX, CY-r), (CX, CY+r)], fill=(255,0,0), width=6)
    draw.rectangle([(CX+15, CY-55), (CX+230, CY-15)], fill=(0,0,0,220))
    draw.text((CX+22, CY-48), "assumed (0,0)", fill=(255,80,80), font=font)

    im.save(out_path, quality=85)
    os.remove(tmp)
    print(f"saved: {out_path}  size: {W}x{H}")

OUT_DIR = r"D:\META\nearmiss\runs"
os.makedirs(OUT_DIR, exist_ok=True)
grid_overlay(r"D:\META\nearmiss\data\fluid\videos\20250120_video.mp4", os.path.join(OUT_DIR, "calib_20250120.jpg"), 400.0)
grid_overlay(r"D:\META\nearmiss\data\fluid\videos\20250525_video.mp4", os.path.join(OUT_DIR, "calib_20250525.jpg"), 200.0)
