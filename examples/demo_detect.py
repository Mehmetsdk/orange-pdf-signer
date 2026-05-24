"""Demo script: detect signature areas and save a debug image with rectangles.

Usage:
  python examples/demo_detect.py input.pdf 0 signature_debug.png

This will load page 0 of input.pdf, detect probable signature areas and
save a rendered page with red rectangles drawn around detected areas.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pdf_backend import load_pdf, find_signature_areas, render_page, rect_points_to_pixels
from PIL import ImageDraw


def draw_areas(pdf_path: str, page: int, out_image: str, dpi: int = 150) -> None:
    doc = load_pdf(pdf_path)
    try:
        areas = find_signature_areas(doc, page)
        img = render_page(doc, page, dpi=dpi).convert("RGBA")
        draw = ImageDraw.Draw(img)

        for a in areas:
            px = rect_points_to_pixels(a, dpi)
            x = px["x"]
            y = px["y"]
            w = px["w"]
            h = px["h"]
            draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 0, 200), width=3)

        img.save(out_image)
        print("Saved debug image:", out_image)
    finally:
        doc.close()


def main(argv):
    if len(argv) < 4:
        print("Usage: python examples/demo_detect.py input.pdf page_number out.png")
        return 2
    pdf = argv[1]
    page = int(argv[2])
    out = argv[3]
    draw_areas(pdf, page, out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
