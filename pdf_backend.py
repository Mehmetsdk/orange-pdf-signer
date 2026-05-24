import argparse
import io
import json
import logging
import os
import re
from typing import Dict, List, Optional

import fitz  # PyMuPDF
from PIL import Image

SIGNATURE_KEYWORDS = [
    "signature", "imza", "sign here", "buraya imza",
    "authorized signature", "yetkili imza", "imzası"
]

logger = logging.getLogger(__name__)


def _validate_page_number(doc: fitz.Document, page_number: int) -> None:
    if page_number < 0 or page_number >= len(doc):
        raise IndexError(f"Page number out of range: {page_number} (0..{len(doc)-1})")


def _normalize_token(token: str) -> str:
    return re.sub(r"\W+", "", token.casefold())


def points_to_pixels(value: float, dpi: int) -> float:
    """Convert a PDF point value to pixels for a given DPI."""
    if dpi <= 0:
        raise ValueError("dpi must be > 0")
    return value * dpi / 72.0


def pixels_to_points(value: float, dpi: int) -> float:
    """Convert a pixel value to PDF points for a given DPI."""
    if dpi <= 0:
        raise ValueError("dpi must be > 0")
    return value * 72.0 / dpi


def rect_points_to_pixels(rect: Dict[str, float], dpi: int) -> Dict[str, float]:
    """Convert rect keys x,y,w,h from PDF points to pixels."""
    return {
        "x": points_to_pixels(rect["x"], dpi),
        "y": points_to_pixels(rect["y"], dpi),
        "w": points_to_pixels(rect["w"], dpi),
        "h": points_to_pixels(rect["h"], dpi),
    }


def rect_pixels_to_points(rect: Dict[str, float], dpi: int) -> Dict[str, float]:
    """Convert rect keys x,y,w,h from pixels to PDF points."""
    return {
        "x": pixels_to_points(rect["x"], dpi),
        "y": pixels_to_points(rect["y"], dpi),
        "w": pixels_to_points(rect["w"], dpi),
        "h": pixels_to_points(rect["h"], dpi),
    }


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
    _validate_page_number(doc, page_number)
    if dpi <= 0:
        raise ValueError("dpi must be > 0")
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
    _validate_page_number(doc, page_number)
    page = doc[page_number]
    found: List[Dict[str, float]] = []

    words = page.get_text("words")
    if words:
        words_sorted = sorted(words, key=lambda w: (w[5], w[6], w[7]))
        tokens = [_normalize_token(w[4]) for w in words_sorted]
        rects = [(w[0], w[1], w[2], w[3]) for w in words_sorted]

        for keyword in SIGNATURE_KEYWORDS:
            parts = [_normalize_token(part) for part in keyword.split()]
            parts = [part for part in parts if part]
            if not parts:
                continue
            n = len(parts)
            for i in range(len(tokens) - n + 1):
                seq = tokens[i:i + n]
                if seq == parts:
                    xs = [r[0] for r in rects[i:i + n]]
                    ys = [r[1] for r in rects[i:i + n]]
                    x1s = [r[2] for r in rects[i:i + n]]
                    y1s = [r[3] for r in rects[i:i + n]]
                    x0 = min(xs)
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

    paths = page.get_drawings()
    page_width = page.rect.width
    for path in paths:
        rect = path.get("rect")
        if rect is None:
            continue
        width = rect.x1 - rect.x0
        height = rect.y1 - rect.y0

        if width > page_width * 0.2 and height < 6:
            area = {
                "x": rect.x0,
                "y": rect.y0 - 35,
                "w": width,
                "h": 35,
                "reason": "Horizontal line (signature line)",
            }
            found.append(area)

    merged: List[Dict[str, float]] = []
    for a in found:
        ax0 = a["x"]
        ay0 = a["y"]
        aw = a["w"]
        ah = a["h"]
        ax1 = ax0 + aw
        ay1 = ay0 + ah

        merged_flag = False
        for m in merged:
            mx0 = m["x"]
            my0 = m["y"]
            mw = m["w"]
            mh = m["h"]
            mx1 = mx0 + mw
            my1 = my0 + mh

            inter_w = max(0, min(ax1, mx1) - max(ax0, mx0))
            inter_h = max(0, min(ay1, my1) - max(ay0, my0))
            inter_area = inter_w * inter_h
            if inter_area > 0:
                nx0 = min(ax0, mx0)
                ny0 = min(ay0, my0)
                nx1 = max(ax1, mx1)
                ny1 = max(ay1, my1)
                m["x"] = nx0
                m["y"] = ny0
                m["w"] = nx1 - nx0
                m["h"] = ny1 - ny0
                m["reason"] += f"; merged {a['reason']}"
                merged_flag = True
                break

        if not merged_flag:
            merged.append(a)

    page_w = page.rect.width
    page_h = page.rect.height
    clamped: List[Dict[str, float]] = []
    for a in merged:
        x = max(0.0, min(a["x"], page_w))
        y = max(0.0, min(a["y"], page_h))
        w = max(0.0, min(a["w"], page_w - x))
        h = max(0.0, min(a["h"], page_h - y))
        if w > 1 and h > 1:
            clamped.append({"x": x, "y": y, "w": w, "h": h, "reason": a["reason"]})

    return clamped


def place_signature(
    pdf_path: str,
    page_no: int,
    x_pt: float,
    y_pt: float,
    signature_img_path: str,
    width_pt: float = 150,
    height_pt: float = 60,
    preserve_aspect_ratio: bool = True,
    output_path: Optional[str] = None,
) -> str:
    """Insert a signature image into a PDF and save the result.

    Coordinates and sizes are in PDF points. The image is inserted at the
    requested top-left origin. If preserve_aspect_ratio is true, the image is
    scaled to fit within the requested rectangle while keeping its ratio.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if width_pt <= 0 or height_pt <= 0:
        raise ValueError("width and height must be > 0")
    if not os.path.exists(signature_img_path):
        raise FileNotFoundError(f"Signature image not found: {signature_img_path}")

    if output_path is None:
        base, ext = os.path.splitext(pdf_path)
        output_path = f"{base}_signed{ext}"

    with Image.open(signature_img_path) as source_img:
        sig_img = source_img.convert("RGBA")

    doc = fitz.open(pdf_path)
    try:
        _validate_page_number(doc, page_no)
        page = doc[page_no]
        page_rect = page.rect
        target_rect = fitz.Rect(x_pt, y_pt, x_pt + width_pt, y_pt + height_pt)
        clipped_rect = target_rect & page_rect
        if clipped_rect.is_empty:
            raise ValueError(
                f"Signature rectangle out of page bounds: page=({page_rect.width:.2f},{page_rect.height:.2f}), "
                f"rect=({x_pt:.2f},{y_pt:.2f},{width_pt:.2f},{height_pt:.2f})"
            )

        if preserve_aspect_ratio:
            scale = min(clipped_rect.width / sig_img.width, clipped_rect.height / sig_img.height)
            scaled_width = max(1, int(round(sig_img.width * scale)))
            scaled_height = max(1, int(round(sig_img.height * scale)))
            resized = sig_img.resize((scaled_width, scaled_height), Image.LANCZOS)
            rect = fitz.Rect(
                clipped_rect.x0,
                clipped_rect.y0,
                clipped_rect.x0 + scaled_width,
                clipped_rect.y0 + scaled_height,
            )
        else:
            resized = sig_img.resize(
                (
                    max(1, int(round(clipped_rect.width))),
                    max(1, int(round(clipped_rect.height))),
                ),
                Image.LANCZOS,
            )
            rect = clipped_rect

        img_bytes = io.BytesIO()
        resized.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        page.insert_image(rect, stream=img_bytes.read(), overlay=True)
        doc.save(output_path)
    finally:
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
    p_place.add_argument("--no-preserve-aspect-ratio", dest="preserve_aspect_ratio", action="store_false")
    p_place.add_argument("--output", help="Output PDF path")
    p_place.set_defaults(preserve_aspect_ratio=True)

    p_convert = sub.add_parser("convert", help="Convert between PDF points and pixels")
    p_convert.add_argument("value", type=float, help="Numeric value to convert")
    p_convert.add_argument("--dpi", type=int, default=150, help="DPI value")
    p_convert.add_argument(
        "--mode",
        choices=["pt2px", "px2pt"],
        default="pt2px",
        help="Conversion mode",
    )

    args = parser.parse_args()

    if args.command == "detect":
        doc = load_pdf(args.pdf)
        try:
            areas = find_signature_areas(doc, args.page)
            _print_json(areas)
        finally:
            doc.close()

    elif args.command == "place":
        out = place_signature(
            args.pdf,
            page_no=args.page,
            x_pt=args.x,
            y_pt=args.y,
            signature_img_path=args.image,
            width_pt=args.width,
            height_pt=args.height,
            preserve_aspect_ratio=args.preserve_aspect_ratio,
            output_path=args.output,
        )
        print(out)

    elif args.command == "convert":
        if args.mode == "pt2px":
            result = points_to_pixels(args.value, args.dpi)
        else:
            result = pixels_to_points(args.value, args.dpi)
        _print_json({"value": args.value, "dpi": args.dpi, "mode": args.mode, "result": result})

    else:
        parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
