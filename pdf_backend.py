import fitz  # PyMuPDF
from PIL import Image
import io
import os
import logging
import argparse
import json
from typing import List, Dict, Optional

SIGNATURE_KEYWORDS = [
    "signature", "imza", "sign here", "buraya imza",
    "authorized signature", "yetkili imza", "imzası"
]

logger = logging.getLogger(__name__)


def load_pdf(pdf_path: str) -> fitz.Document:
    """Open and return a PyMuPDF document.

    Raises FileNotFoundError if the path does not exist.
    """
    if not os.path.exists(pdf_path):
        logger.error("PDF not found: %s", pdf_path)
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return fitz.open(pdf_path)


def get_page_count(doc: fitz.Document) -> int:
    """Return the number of pages in the document."""
    return len(doc)


def render_page(doc: fitz.Document, page_number: int, dpi: int = 150) -> Image.Image:
    """Render a page to a Pillow Image at the requested DPI."""
    page = doc[page_number]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


def find_signature_areas(doc: fitz.Document, page_number: int) -> List[Dict[str, float]]:
    """Try to heuristically find signature areas on a page.

    Returns a list of areas with keys: x, y, w, h, reason.
    Coordinates are in PDF points.
    """
    page = doc[page_number]
    found: List[Dict[str, float]] = []

    # WORD-BASED keyword detection (case-insensitive, handles multi-word keywords)
    words = page.get_text("words")  # list of tuples (x0, y0, x1, y1, "word", block_no, line_no, word_no)
    if words:
        # sort by block/line/word to preserve reading order
        words_sorted = sorted(words, key=lambda w: (w[5], w[6], w[7]))
        tokens = [w[4] for w in words_sorted]
        rects = [(w[0], w[1], w[2], w[3]) for w in words_sorted]

        for keyword in SIGNATURE_KEYWORDS:
            parts = keyword.lower().split()
            n = len(parts)
            for i in range(len(tokens) - n + 1):
                seq = [t.lower() for t in tokens[i:i + n]]
                if seq == parts:
                    xs = [r[0] for r in rects[i:i + n]]
                    ys = [r[1] for r in rects[i:i + n]]
                    x1s = [r[2] for r in rects[i:i + n]]
                    y1s = [r[3] for r in rects[i:i + n]]
                    x0 = min(xs)
                    y0 = min(ys)
                    x1 = max(x1s)
                    y1 = max(y1s)
                    area = {
                        "x": x0,
                        "y": y1 + 2,
                        "w": max((x1 - x0) * 3, 150),
                        "h": 40,
                        "reason": f"Keyword match: '{keyword}'",
                    }
                    found.append(area)

    # Drawing-based detection (horizontal lines)
    paths = page.get_drawings()
    page_width = page.rect.width
    for path in paths:
        rect = path.get("rect")
        if rect is None:
            continue
        width = rect.x1 - rect.x0
        height = rect.y1 - rect.y0

        # line-like drawing: wide and very thin
        if width > page_width * 0.2 and height < 6:
            area = {
                "x": rect.x0,
                "y": rect.y0 - 35,
                "w": width,
                "h": 35,
                "reason": "Horizontal line (signature line)",
            }
            found.append(area)

    # Merge overlapping/nearby areas to reduce duplicates
    merged: List[Dict[str, float]] = []
    for a in found:
        ax0 = a["x"]
        ay1 = a["y"]
        aw = a["w"]
        ah = a["h"]
        ax1 = ax0 + aw
        ay0 = ay1 - ah

        merged_flag = False
        for m in merged:
            mx0 = m["x"]
            my1 = m["y"]
            mw = m["w"]
            mh = m["h"]
            mx1 = mx0 + mw
            my0 = my1 - mh

            inter_w = max(0, min(ax1, mx1) - max(ax0, mx0))
            inter_h = max(0, min(ay1, my1) - max(ay0, my0))
            inter_area = inter_w * inter_h
            if inter_area > 0:
                # merge by expanding bounding box
                nx0 = min(ax0, mx0)
                ny0 = min(ay0, my0)
                nx1 = max(ax1, mx1)
                ny1 = max(ay1, my1)
                m["x"] = nx0
                m["y"] = ny1
                m["w"] = nx1 - nx0
                m["h"] = ny1 - ny0
                m["reason"] += f"; merged {a['reason']}"
                merged_flag = True
                break

        if not merged_flag:
            merged.append(a)

    return merged


def place_signature(
    pdf_path: str,
    page_number: int,
    x: float,
    y: float,
    signature_img_path: str,
    width: float = 150,
    height: float = 60,
    output_path: Optional[str] = None,
) -> str:
    """Insert a signature image into a PDF and save the result.

    Keeps coordinates in PDF points. The signature image is resized to a
    reasonable size and inserted into the given rectangle.
    Returns the path to the saved PDF.
    """
    doc = fitz.open(pdf_path)
    page = doc[page_number]

    if not os.path.exists(signature_img_path):
        raise FileNotFoundError(f"Signature image not found: {signature_img_path}")

    sig_img = Image.open(signature_img_path).convert("RGBA")
    sig_img = sig_img.resize((int(width * 2), int(height * 2)), Image.LANCZOS)

    img_bytes = io.BytesIO()
    sig_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    rect = fitz.Rect(x, y, x + width, y + height)
    page.insert_image(rect, stream=img_bytes.read(), overlay=True)

    if output_path is None:
        base, ext = os.path.splitext(pdf_path)
        output_path = f"{base}_signed{ext}"

    doc.save(output_path)
    doc.close()
    logger.info("Saved signed PDF to %s", output_path)
    return output_path




def _print_json(obj: object) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF signature helper utilities")
    sub = parser.add_subparsers(dest="command")

    p_detect = sub.add_parser("detect", help="Detect signature areas on a page")
    p_detect.add_argument("pdf", help="Path to PDF")
    p_detect.add_argument("page", type=int, help="0-based page number")

    p_place = sub.add_parser("place", help="Place a signature image into a PDF")
    p_place.add_argument("pdf", help="Path to PDF")
    p_place.add_argument("page", type=int, help="0-based page number")
    p_place.add_argument("x", type=float, help="x (points)")
    p_place.add_argument("y", type=float, help="y (points)")
    p_place.add_argument("image", help="Signature image path")
    p_place.add_argument("--width", type=float, default=150.0, help="Width in points")
    p_place.add_argument("--height", type=float, default=60.0, help="Height in points")
    p_place.add_argument("--output", help="Output PDF path")

    args = parser.parse_args()

    if args.command == "detect":
        doc = load_pdf(args.pdf)
        areas = find_signature_areas(doc, args.page)
        _print_json(areas)

    elif args.command == "place":
        out = place_signature(
            args.pdf,
            args.page,
            args.x,
            args.y,
            args.image,
            width=args.width,
            height=args.height,
            output_path=args.output,
        )
        print(out)

    else:
        parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
