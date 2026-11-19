"""Convierte assets\\icono.png en assets\\icono.ico con varios tamanos (16 a 256 px).

Uso: python tools\\convertir_icono.py
Requiere Pillow: pip install pillow
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ORIGEN = ROOT / "assets" / "icono.png"
DESTINO = ROOT / "assets" / "icono.ico"
TAMANOS = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    if not ORIGEN.is_file():
        raise SystemExit(f"No encontre {ORIGEN}. Guarda tu imagen con ese nombre (PNG cuadrado, 512x512 o mas).")
    imagen = Image.open(ORIGEN).convert("RGBA")
    imagen.save(DESTINO, sizes=TAMANOS)
    print(f"Creado: {DESTINO}")


if __name__ == "__main__":
    main()