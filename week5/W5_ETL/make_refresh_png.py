"""Turns outputs/run_report.txt into the before/after picture for the refresh test.
Python track has no Power BI card to screenshot, so this is the script's own output, nothing re-typed.
Run after W5_BSDS030.py.  (Kamran Khan Hussain | BSDS030)
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

lines = Path("outputs/run_report.txt").read_text(encoding="utf-8").splitlines()


def block(start_pat, end_pat):
    s = next(i for i, l in enumerate(lines) if start_pat in l)
    e = next(i for i, l in enumerate(lines) if i > s and end_pat in l)
    return lines[s:e + 1]


before = block("the eight checks - night1", "6  rows routed to Unknown")
after = block("refresh check", "duplicates removed on night2")
summary = [l for l in lines if l.startswith("  night1:") or l.startswith("  night2:")]

mono = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
bold = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
font, font_b = ImageFont.truetype(mono, 15), ImageFont.truetype(bold, 16)
lh, pad = 21, 22

panels = [("BEFORE  -  night one  (python W5_BSDS030.py, source/)", before),
          ("AFTER  -  night two  (same code, source/night2/)", after + [""] + summary)]
width = max(1000, int(max(font.getlength(l) for _, p in panels for l in p)) + pad * 2)
height = pad * 2 + sum((len(p) + 3) * lh for _, p in panels) + 30

img = Image.new("RGB", (width, height), (22, 27, 34))
d = ImageDraw.Draw(img)
y = pad
d.text((pad, y), "Kamran Khan Hussain | BSDS030 | 7A | W5 ETL lab, Python track | output of W5_BSDS030.py",
       font=font, fill=(130, 140, 155))
y += lh + 12
for title, body in panels:
    colour = (31, 111, 235) if title.startswith("BEFORE") else (35, 134, 54)
    d.rectangle([pad - 6, y - 4, width - pad + 6, y + lh + 2], fill=colour)
    d.text((pad, y), title, font=font_b, fill=(255, 255, 255))
    y += lh + 10
    for line in body:
        ink = (230, 237, 243)
        if "FAIL" in line:
            ink = (255, 123, 114)
        elif line.strip().endswith("pass"):
            ink = (126, 231, 135)
        d.text((pad, y), line, font=font, fill=ink)
        y += lh
    y += lh
img.crop((0, 0, width, y + 6)).save("outputs/refresh_test_before_after.png")
print("saved outputs/refresh_test_before_after.png", img.size)
