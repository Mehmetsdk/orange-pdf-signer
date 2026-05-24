"""Demo script: detect a signature area and place a signature image there.

Usage:
  python examples/demo_place.py examples/sample.pdf 0 examples/signature.png out.pdf out.png

This will detect the first signature area on the page, overlay the signature
image and save a signed PDF and a rendered PNG preview.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pdf_backend import load_pdf, find_signature_areas, place_signature, render_page


def place_and_preview(pdf_path: str, page: int, sig_img: str, out_pdf: str, out_img: str):
    doc = load_pdf(pdf_path)
    try:
        areas = find_signature_areas(doc, page)
    finally:
        doc.close()

    if not areas:
        raise RuntimeError("No signature areas detected")

    a = areas[0]
    x = a["x"]
    y = a["y"]
    w = a["w"]
    h = a["h"]

    # Slightly reduce size so image fits nicely over the area.
    out_pdf_path = place_signature(pdf_path, page, x, y, sig_img, width=w * 0.9, height=h * 0.9, output_path=out_pdf)

    # Render preview.
    doc2 = load_pdf(out_pdf_path)
    try:
        img = render_page(doc2, page, dpi=150)
        img.save(out_img)
    finally:
        doc2.close()
    print("Saved signed PDF:", out_pdf_path)
    print("Saved preview image:", out_img)


def main(argv):
    if len(argv) < 6:
        print("Usage: python examples/demo_place.py input.pdf page signature.png out.pdf out.png")
        return 2
    pdf = argv[1]
    page = int(argv[2])
    sig = argv[3]
    outpdf = argv[4]
    outimg = argv[5]
    place_and_preview(pdf, page, sig, outpdf, outimg)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
