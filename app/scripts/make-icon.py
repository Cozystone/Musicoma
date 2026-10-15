"""build/icon.svg 와 같은 그림을 Pillow 로 그려 build/icon.png(256) + build/icon.ico 를 만든다."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "build"
S = 1024                       # 4배로 그려서 축소(안티앨리어싱)
k = S / 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([8 * k, 8 * k, 248 * k, 248 * k], radius=48 * k, fill="#1e1e1e")
font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", int(150 * k))
d.text((112 * k, 182 * k), "M", font=font, fill="#e6a31a", anchor="ms")
r = 14 * k
d.ellipse([205 * k - r, 170 * k - r, 205 * k + r, 170 * k + r], fill="#e6a31a")
png = img.resize((256, 256), Image.LANCZOS)
png.save(OUT / "icon.png")
png.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok", OUT)
