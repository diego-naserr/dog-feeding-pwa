"""Genera los íconos PNG de la PWA (paw print simple). Correr una vez:
python make_icons.py
"""
from PIL import Image, ImageDraw

BLUE = (29, 78, 216, 255)  # --primary
WHITE = (255, 255, 255, 255)


def draw_paw(draw, size, scale=1.0):
    cx, cy = size / 2, size * 0.58
    pad_w, pad_h = size * 0.30 * scale, size * 0.24 * scale
    draw.ellipse([cx - pad_w / 2, cy - pad_h / 2, cx + pad_w / 2, cy + pad_h / 2], fill=WHITE)

    toe_r = size * 0.09 * scale
    offsets = [(-0.20, -0.28), (-0.075, -0.34), (0.075, -0.34), (0.20, -0.28)]
    for dx, dy in offsets:
        tx = size / 2 + dx * size * scale
        ty = size / 2 + dy * size * scale
        draw.ellipse([tx - toe_r, ty - toe_r, tx + toe_r, ty + toe_r], fill=WHITE)


def make_icon(size, path, maskable=False):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if maskable:
        draw.rectangle([0, 0, size, size], fill=BLUE)
        draw_paw(draw, size, scale=0.65)
    else:
        radius = int(size * 0.22)
        draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BLUE)
        draw_paw(draw, size, scale=1.0)

    img.save(path)


if __name__ == "__main__":
    make_icon(192, "static/icons/icon-192.png")
    make_icon(512, "static/icons/icon-512.png")
    make_icon(512, "static/icons/icon-maskable.png", maskable=True)
    print("Íconos generados en static/icons/")
