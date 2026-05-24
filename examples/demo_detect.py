"""Demo script: detect signature areas and save a debug image with rectangles.

Usage:
  python examples/demo_detect.py input.pdf 0 signature_debug.png

This will load page 0 of input.pdf, detect probable signature areas and
save a rendered page with red rectangles drawn around detected areas.
"""
import sys
from pdf_backend import load_pdf, find_signature_areas, render_page
from PIL import ImageDraw


def draw_areas(pdf_path: str, page: int, out_image: str, dpi: int = 150) -> None:
    doc = load_pdf(pdf_path)
    areas = find_signature_areas(doc, page)
    img = render_page(doc, page, dpi=dpi).convert("RGBA")
    draw = ImageDraw.Draw(img)

    scale = dpi / 72.0
    for a in areas:
        x = a["x"] * scale
        y_top = (a["y"] - a["h"]) * scale
        w = a["w"] * scale
        h = a["h"] * scale
        draw.rectangle([x, y_top, x + w, y_top + h], outline=(255, 0, 0, 200), width=3)

    img.save(out_image)
    print("Saved debug image:", out_image)


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
