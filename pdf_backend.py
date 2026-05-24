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


# ── Internal helpers ──────────────────────────────────────────────────────────

def _validate_page_number(doc: fitz.Document, page_number: int) -> None:
    if page_number < 0 or page_number >= len(doc):
        raise IndexError(f"Page number out of range: {page_number} (0..{len(doc)-1})")


def _normalize_token(token: str) -> str:
    return re.sub(r"\W+", "", token.casefold())


# ── Unit conversion ───────────────────────────────────────────────────────────

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


def pt_to_px(pt_value: float, dpi: int = 150) -> float:
    return pt_value * (dpi / 72)


def px_to_pt(px_value: float, dpi: int = 150) -> float:
    return px_value * (72 / dpi)


def rect_points_to_pixels(rect: Dict[str, float], dpi: int) -> Dict[str, float]:
    return {
        "x": points_to_pixels(rect["x"], dpi),
        "y": points_to_pixels(rect["y"], dpi),
        "w": points_to_pixels(rect["w"], dpi),
        "h": points_to_pixels(rect["h"], dpi),
    }


def rect_pixels_to_points(rect: Dict[str, float], dpi: int) -> Dict[str, float]:
    return {
        "x": pixels_to_points(rect["x"], dpi),
        "y": pixels_to_points(rect["y"], dpi),
        "w": pixels_to_points(rect["w"], dpi),
        "h": pixels_to_points(rect["h"], dpi),
    }


# ── PDF loading and rendering ─────────────────────────────────────────────────

def load_pdf(pdf_path: str) -> fitz.Document:
    """Open and return a PyMuPDF document."""
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


# ── Signature area detection ──────────────────────────────────────────────────

def find_signature_areas(doc: fitz.Document, page_number: int) -> List[Dict[str, float]]:
    """Heuristically find signature areas on a page.

    Öncelik sırası:
    1. Yatay çizgi + yakın anahtar kelime → çizginin hemen üstüne yerleştir
    2. Sadece yatay çizgi → çizginin üstüne yerleştir
    3. Sadece anahtar kelime → kelimenin sağına yerleştir

    Returns a list of areas with keys: x, y, w, h, reason.
    Coordinates are in PDF points.
    """
    _validate_page_number(doc, page_number)
    page = doc[page_number]
    page_w = page.rect.width
    page_h = page.rect.height
    SIG_H = 36  # imza yüksekliği (pt)

    # ── 1. Yatay çizgileri bul (grafik çizgiler) ────────────────────────────
    lines = []
    for path in page.get_drawings():
        rect = path.get("rect")
        if rect is None:
            continue
        w = rect.x1 - rect.x0
        h = rect.y1 - rect.y0
        if w > page_w * 0.1 and h < 6:
            lines.append({"x0": rect.x0, "x1": rect.x1, "y0": rect.y0, "y1": rect.y1})

    # ── 2. Anahtar kelimeleri ve metin tabanlı alt çizgileri bul ────────────
    keyword_hits = []
    words = page.get_text("words")
    if words:
        words_sorted = sorted(words, key=lambda w: (w[5], w[6], w[7]))
        tokens = [_normalize_token(w[4]) for w in words_sorted]
        rects  = [(w[0], w[1], w[2], w[3]) for w in words_sorted]
        # Metin tabanlı alt çizgiler: "____" veya "----" gibi karakterler
        for word in words_sorted:
            text = word[4].strip()
            if len(text) >= 3 and all(c in '_-' for c in text):
                lines.append({
                    "x0": word[0], "x1": word[2],
                    "y0": word[1], "y1": word[3],
                })

        for keyword in SIGNATURE_KEYWORDS:
            parts = [_normalize_token(p) for p in keyword.split() if _normalize_token(p)]
            if not parts:
                continue
            n = len(parts)
            for i in range(len(tokens) - n + 1):
                if tokens[i:i + n] == parts:
                    kx0 = min(r[0] for r in rects[i:i + n])
                    kx1 = max(r[2] for r in rects[i:i + n])
                    ky0 = min(r[1] for r in rects[i:i + n])
                    ky1 = max(r[3] for r in rects[i:i + n])
                    keyword_hits.append({
                        "kx0": kx0, "kx1": kx1, "ky0": ky0, "ky1": ky1,
                        "keyword": keyword,
                    })

    # ── 3. Her anahtar kelime için en yakın çizgiyi eşleştir ────────────────
    found: List[Dict[str, float]] = []
    used_line_indices: set = set()

    for kh in keyword_hits:
        ky_mid = (kh["ky0"] + kh["ky1"]) / 2
        best_idx, best_line, best_dist = None, None, float("inf")
        for i, line in enumerate(lines):
            line_y_mid = (line["y0"] + line["y1"]) / 2
            # Çizgi: kelimeyle aynı satırda veya hemen altında, kelimeden sağda başlıyor
            if abs(line_y_mid - ky_mid) < 25 and line["x1"] > kh["kx0"]:
                dist = abs(line_y_mid - ky_mid)
                if dist < best_dist:
                    best_dist, best_idx, best_line = dist, i, line
        if best_line is not None:
            # Çizginin hemen üstüne, çizgi genişliğinde — imza çizgiye oturur
            used_line_indices.add(best_idx)
            line_w = best_line["x1"] - best_line["x0"]
            found.append({
                "x": best_line["x0"],
                "y": best_line["y0"] - SIG_H,
                "w": max(line_w, 100),
                "h": SIG_H,
                "reason": f"Keyword: '{kh['keyword']}' + line",
            })
        else:
            # Yakın çizgi yok → kelimenin sağına yerleştir
            text_h = kh["ky1"] - kh["ky0"]
            h = max(text_h + 10, SIG_H)
            found.append({
                "x": kh["kx1"] + 5,
                "y": kh["ky0"] - (h - text_h) / 2,
                "w": max(150, page_w - kh["kx1"] - 30),
                "h": h,
                "reason": f"Keyword: '{kh['keyword']}'",
            })

    # ── 4. Eşleşmemiş çizgileri de ekle ─────────────────────────────────────
    for i, line in enumerate(lines):
        if i not in used_line_indices:
            found.append({
                "x": line["x0"],
                "y": line["y0"] - SIG_H,
                "w": line["x1"] - line["x0"],
                "h": SIG_H,
                "reason": "Horizontal line (signature line)",
            })

    # ── 5. Çakışanları birleştir ─────────────────────────────────────────────
    merged: List[Dict[str, float]] = []
    for a in found:
        ax0, ay0 = a["x"], a["y"]
        ax1, ay1 = ax0 + a["w"], ay0 + a["h"]
        did_merge = False
        for m in merged:
            mx0, my0 = m["x"], m["y"]
            mx1, my1 = mx0 + m["w"], my0 + m["h"]
            if max(0, min(ax1, mx1) - max(ax0, mx0)) * max(0, min(ay1, my1) - max(ay0, my0)) > 0:
                nx0, ny0 = min(ax0, mx0), min(ay0, my0)
                m["x"], m["y"] = nx0, ny0
                m["w"] = max(ax1, mx1) - nx0
                m["h"] = max(ay1, my1) - ny0
                m["reason"] += f" + {a['reason']}"
                did_merge = True
                break
        if not did_merge:
            merged.append(dict(a))

    # ── 6. Sayfa sınırlarına kırp ────────────────────────────────────────────
    result: List[Dict[str, float]] = []
    for a in merged:
        x = max(0.0, min(float(a["x"]), page_w))
        y = max(0.0, min(float(a["y"]), page_h))
        w = max(0.0, min(float(a["w"]), page_w - x))
        h = max(0.0, min(float(a["h"]), page_h - y))
        if w > 1 and h > 1:
            result.append({"x": x, "y": y, "w": w, "h": h, "reason": a["reason"]})

    return result


# ── Signature image processing ────────────────────────────────────────────────

def rembg_is_available() -> bool:
    try:
        import rembg  # noqa: F401
        return True
    except (ImportError, SystemExit, Exception):
        return False


def remove_light_background_pillow(image: Image.Image, white_threshold: int = 245) -> Image.Image:
    """Remove near-white pixels and make them transparent."""
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if r > white_threshold and g > white_threshold and b > white_threshold:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def apply_opacity(image: Image.Image, opacity: float) -> Image.Image:
    opacity = max(0.0, min(1.0, float(opacity)))
    rgba = image.convert("RGBA")
    r, g, b, a = rgba.split()
    a = a.point(lambda v: int(v * opacity))
    return Image.merge("RGBA", (r, g, b, a))


def trim_transparent_edges(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.split()[3]
    bbox = alpha.getbbox()
    if bbox:
        return rgba.crop(bbox)
    return rgba


def resize_signature_to_box(
    image: Image.Image,
    width_px: int,
    height_px: int,
    preserve_aspect_ratio: bool = True,
) -> Image.Image:
    width_px = max(1, int(width_px))
    height_px = max(1, int(height_px))
    rgba = image.convert("RGBA")
    if preserve_aspect_ratio:
        fitted = rgba.copy()
        fitted.thumbnail((width_px, height_px), Image.LANCZOS)
        canvas = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))
        offset = ((width_px - fitted.width) // 2, (height_px - fitted.height) // 2)
        canvas.paste(fitted, offset, fitted)
        return canvas
    return rgba.resize((width_px, height_px), Image.LANCZOS)


def process_signature_image(
    image: Image.Image,
    remove_background: bool = False,
    use_rembg: bool = True,
    white_threshold: int = 245,
    opacity: float = 1.0,
    rotation_degrees: float = 0,
    trim_transparent: bool = True,
    info: dict | None = None,
) -> Image.Image:
    """Process a signature image and return RGBA."""
    meta = {"used_rembg": False, "rembg_failed": False, "pillow_fallback": False, "error": None}
    try:
        result = image.convert("RGBA")
        if remove_background:
            removed = False
            if use_rembg:
                try:
                    from rembg import remove as rembg_remove
                    buf = io.BytesIO()
                    result.save(buf, format="PNG")
                    out_bytes = rembg_remove(buf.getvalue())
                    result = Image.open(io.BytesIO(out_bytes)).convert("RGBA")
                    meta["used_rembg"] = True
                    removed = True
                except (Exception, SystemExit):
                    meta["rembg_failed"] = True
            if not removed:
                result = remove_light_background_pillow(result, white_threshold)
                meta["pillow_fallback"] = True
        if opacity != 1.0:
            result = apply_opacity(result, opacity)
        if rotation_degrees != 0:
            result = result.rotate(rotation_degrees, expand=True, resample=Image.BICUBIC)
        if trim_transparent:
            result = trim_transparent_edges(result)
        if info is not None:
            info.update(meta)
        return result.convert("RGBA")
    except Exception as exc:
        meta["error"] = str(exc)
        if info is not None:
            info.update(meta)
        try:
            return image.convert("RGBA")
        except Exception:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))


def pil_image_to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGBA").save(buf, format="PNG")
    return buf.getvalue()


# ── Signature placement ───────────────────────────────────────────────────────

def place_signature(
    pdf_path: str,
    page_number: int,
    x_pt: float,
    y_pt: float,
    signature_img_path: str,
    width: float = 150,
    height: float = 60,
    preserve_aspect_ratio: bool = True,
    output_path: Optional[str] = None,
) -> str:
    """Insert a signature image into a PDF and save the result."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if width <= 0 or height <= 0:
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
        _validate_page_number(doc, page_number)
        page = doc[page_number]
        page_rect = page.rect
        target_rect = fitz.Rect(x_pt, y_pt, x_pt + width, y_pt + height)
        clipped_rect = target_rect & page_rect

        if clipped_rect.is_empty:
            raise ValueError(
                f"Signature rectangle out of page bounds: "
                f"page=({page_rect.width:.2f},{page_rect.height:.2f}), "
                f"rect=({x_pt:.2f},{y_pt:.2f},{width:.2f},{height:.2f})"
            )

        if preserve_aspect_ratio:
            scale = min(clipped_rect.width / sig_img.width, clipped_rect.height / sig_img.height)
            scaled_w = max(1, int(round(sig_img.width * scale)))
            scaled_h = max(1, int(round(sig_img.height * scale)))
            resized = sig_img.resize((scaled_w, scaled_h), Image.LANCZOS)
            rect = fitz.Rect(clipped_rect.x0, clipped_rect.y0, clipped_rect.x0 + scaled_w, clipped_rect.y0 + scaled_h)
        else:
            resized = sig_img.resize((max(1, int(round(clipped_rect.width))), max(1, int(round(clipped_rect.height)))), Image.LANCZOS)
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


# ── Position helpers ──────────────────────────────────────────────────────────

def clamp_signature_position(
    x_pt: float, y_pt: float,
    page_width_pt: float, page_height_pt: float,
    sig_width_pt: float, sig_height_pt: float,
) -> tuple[float, float]:
    max_x = max(0.0, float(page_width_pt) - float(sig_width_pt))
    max_y = max(0.0, float(page_height_pt) - float(sig_height_pt))
    return (min(max(0.0, float(x_pt)), max_x), min(max(0.0, float(y_pt)), max_y))


def click_center_to_signature_top_left_pt(
    center_x_pt: float, center_y_pt: float,
    sig_width_pt: float, sig_height_pt: float,
    page_width_pt: float, page_height_pt: float,
) -> tuple[float, float]:
    x_pt = float(center_x_pt) - float(sig_width_pt) / 2
    y_pt = float(center_y_pt) - float(sig_height_pt) / 2
    return clamp_signature_position(x_pt, y_pt, page_width_pt, page_height_pt, sig_width_pt, sig_height_pt)


def display_click_to_signature_top_left_pt(
    click_x: float, click_y: float,
    display_width: int, display_height: int,
    rendered_width: int, rendered_height: int,
    sig_width_pt: float, sig_height_pt: float,
    page_width_pt: float, page_height_pt: float,
    dpi: int = 150,
) -> tuple[float, float]:
    rendered_x_px = click_x * (rendered_width / display_width)
    rendered_y_px = click_y * (rendered_height / display_height)
    center_x_pt = px_to_pt(rendered_x_px, dpi)
    center_y_pt = px_to_pt(rendered_y_px, dpi)
    return click_center_to_signature_top_left_pt(
        center_x_pt, center_y_pt,
        sig_width_pt, sig_height_pt,
        page_width_pt, page_height_pt,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_json(obj: object) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF signature helper utilities")
    sub = parser.add_subparsers(dest="command")

    p_detect = sub.add_parser("detect", help="Detect signature areas on a page")
    p_detect.add_argument("pdf", help="Path to PDF")
    p_detect.add_argument("page", type=int, help="0-based page number")

    p_place = sub.add_parser("place", help="Place a signature image into a PDF")
    p_place.add_argument("pdf")
    p_place.add_argument("page", type=int)
    p_place.add_argument("x", type=float)
    p_place.add_argument("y", type=float)
    p_place.add_argument("image")
    p_place.add_argument("--width", type=float, default=150.0)
    p_place.add_argument("--height", type=float, default=60.0)
    p_place.add_argument("--output")

    p_convert = sub.add_parser("convert", help="Convert between PDF points and pixels")
    p_convert.add_argument("value", type=float)
    p_convert.add_argument("--dpi", type=int, default=150)
    p_convert.add_argument("--mode", choices=["pt2px", "px2pt"], default="pt2px")

    args = parser.parse_args()

    if args.command == "detect":
        doc = load_pdf(args.pdf)
        try:
            areas = find_signature_areas(doc, args.page)
            _print_json(areas)
        finally:
            doc.close()

    elif args.command == "place":
        out = place_signature(args.pdf, args.page, args.x, args.y, args.image,
                              width=args.width, height=args.height, output_path=args.output)
        print(out)

    elif args.command == "convert":
        result = points_to_pixels(args.value, args.dpi) if args.mode == "pt2px" else pixels_to_points(args.value, args.dpi)
        _print_json({"value": args.value, "dpi": args.dpi, "mode": args.mode, "result": result})

    else:
        parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
