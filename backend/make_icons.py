"""Genera los iconos de la PWA y la imagen del header/banner a partir de
una foto real de los perros. Correr una vez (o cuando cambie la foto):

    python make_icons.py ruta/a/la/foto.jpg

Guarda la copia optimizada en static/images/perritos.jpg y genera:
- static/icons/icon-192.png
- static/icons/icon-512.png
- static/icons/icon-maskable.png (con margen de seguridad para el recorte
  que hacen Android/iOS al aplicar la mascara del icono)
"""
import sys
from pathlib import Path

from PIL import Image, ImageOps

STATIC = Path(__file__).resolve().parent / "static"
SOURCE_DEFAULT = STATIC / "images" / "perritos.jpg"


def load_square(path: Path) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    return img.crop((left, top, left + side, top + side))


def save_web_copy(img: Image.Image) -> None:
    web = img.resize((800, 800), Image.LANCZOS)
    out = STATIC / "images" / "perritos.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    web.save(out, "JPEG", quality=85, optimize=True)
    print(f"Copia web guardada: {out} ({out.stat().st_size // 1024} KB)")


def make_icon(img: Image.Image, size: int, path: Path) -> None:
    resized = img.resize((size, size), Image.LANCZOS)
    resized.save(path, "PNG")
    print(f"Icono generado: {path}")


def make_maskable_icon(img: Image.Image, size: int, path: Path) -> None:
    """La mascara del sistema puede recortar hasta un ~20% del borde, asi
    que la foto se achica al ~72% central y el resto se rellena con un
    fondo solido (tomado de la esquina de la foto) para que no queden
    bordes duros ni se pierda a los perros en el recorte."""
    bg_color = img.resize((1, 1), Image.LANCZOS).getpixel((0, 0))
    canvas = Image.new("RGB", (size, size), bg_color)

    inner = int(size * 0.72)
    photo = img.resize((inner, inner), Image.LANCZOS)
    offset = (size - inner) // 2
    canvas.paste(photo, (offset, offset))
    canvas.save(path, "PNG")
    print(f"Icono maskable generado: {path}")


def main() -> None:
    icons_dir = STATIC / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1:
        square = load_square(Path(sys.argv[1]))
        save_web_copy(square)
    elif SOURCE_DEFAULT.exists():
        square = load_square(SOURCE_DEFAULT)
    else:
        print(f"Falta la foto. Pasala como argumento o dejala en {SOURCE_DEFAULT}")
        sys.exit(1)

    make_icon(square, 192, icons_dir / "icon-192.png")
    make_icon(square, 512, icons_dir / "icon-512.png")
    make_maskable_icon(square, 512, icons_dir / "icon-maskable.png")
    print("Listo.")


if __name__ == "__main__":
    main()
