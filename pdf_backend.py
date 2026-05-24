import fitz  # PyMuPDF
from PIL import Image
import io
import os

SIGNATURE_KEYWORDS = [
    "signature", "imza", "sign here", "buraya imza",
    "authorized signature", "yetkili imza", "imzası"
]


def load_pdf(pdf_path: str) -> fitz.Document:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return fitz.open(pdf_path)


def get_page_count(doc: fitz.Document) -> int:
    return len(doc)


def render_page(doc: fitz.Document, page_number: int, dpi: int = 150) -> Image.Image:
    page = doc[page_number]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


def find_signature_areas(doc: fitz.Document, page_number: int) -> list:
    page = doc[page_number]
    found = []

    for keyword in SIGNATURE_KEYWORDS:
        instances = page.search_for(keyword)
        for rect in instances:
            area = {
                "x": rect.x0,
                "y": rect.y1 + 2,
                "w": max(rect.width * 3, 150),
                "h": 40,
                "reason": f"Keyword match: '{keyword}'"
            }
            found.append(area)

    paths = page.get_drawings()
    page_width = page.rect.width

    for path in paths:
        rect = path["rect"]
        width = rect.x1 - rect.x0
        height = rect.y1 - rect.y0

        if width > page_width * 0.2 and height < 5:
            area = {
                "x": rect.x0,
                "y": rect.y0 - 35,
                "w": width,
                "h": 35,
                "reason": "Horizontal line (signature line)"
            }
            found.append(area)

    return found


def rembg_is_available() -> bool:
    try:
        import rembg  # noqa: F401
        return True
    except ImportError:
        return False


def remove_light_background_pillow(
    image: Image.Image,
    white_threshold: int = 245,
) -> Image.Image:
    """Remove near-white pixels; keep existing transparency on PNGs."""
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
        offset = (
            (width_px - fitted.width) // 2,
            (height_px - fitted.height) // 2,
        )
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
    """
    Process a signature image and return RGBA.
    Optional `info` dict receives keys: used_rembg, rembg_failed, pillow_fallback.
    """
    meta = {
        "used_rembg": False,
        "rembg_failed": False,
        "pillow_fallback": False,
        "error": None,
    }

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
                except Exception:
                    meta["rembg_failed"] = True

            if not removed:
                result = remove_light_background_pillow(result, white_threshold)
                meta["pillow_fallback"] = True

        if opacity != 1.0:
            result = apply_opacity(result, opacity)

        if rotation_degrees != 0:
            result = result.rotate(
                rotation_degrees,
                expand=True,
                resample=Image.BICUBIC,
            )

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


def place_signature(
    pdf_path,
    page_number,
    x,
    y,
    signature_img_path,
    width=150,
    height=60,
    preserve_aspect_ratio=True,
    output_path=None,
):
    if not os.path.exists(signature_img_path):
        raise FileNotFoundError(f"Signature image not found: {signature_img_path}")
    sig_img = Image.open(signature_img_path).convert("RGBA")
    return place_signature_image(
        pdf_path,
        page_number,
        x,
        y,
        sig_img,
        width=width,
        height=height,
        preserve_aspect_ratio=preserve_aspect_ratio,
        output_path=output_path,
    )


def place_signature_image(
    pdf_path,
    page_number,
    x,
    y,
    signature_image: Image.Image,
    width=150,
    height=60,
    preserve_aspect_ratio=True,
    output_path=None,
):
    """Insert a PIL RGBA signature into a PDF page; PNG alpha is preserved."""
    doc = fitz.open(pdf_path)
    page = doc[page_number]

    sig_img = resize_signature_to_box(
        signature_image,
        max(1, int(width * 2)),
        max(1, int(height * 2)),
        preserve_aspect_ratio=preserve_aspect_ratio,
    )

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
    return output_path


def pt_to_px(pt_value: float, dpi: int = 150) -> float:
    return pt_value * (dpi / 72)


def px_to_pt(px_value: float, dpi: int = 150) -> float:
    return px_value * (72 / dpi)


def clamp_signature_position(
    x_pt: float,
    y_pt: float,
    page_width_pt: float,
    page_height_pt: float,
    sig_width_pt: float,
    sig_height_pt: float,
) -> tuple[float, float]:
    max_x = max(0.0, float(page_width_pt) - float(sig_width_pt))
    max_y = max(0.0, float(page_height_pt) - float(sig_height_pt))
    return (
        min(max(0.0, float(x_pt)), max_x),
        min(max(0.0, float(y_pt)), max_y),
    )


def click_center_to_signature_top_left_pt(
    center_x_pt: float,
    center_y_pt: float,
    sig_width_pt: float,
    sig_height_pt: float,
    page_width_pt: float,
    page_height_pt: float,
) -> tuple[float, float]:
    x_pt = float(center_x_pt) - float(sig_width_pt) / 2
    y_pt = float(center_y_pt) - float(sig_height_pt) / 2
    return clamp_signature_position(
        x_pt,
        y_pt,
        page_width_pt,
        page_height_pt,
        sig_width_pt,
        sig_height_pt,
    )


def display_click_to_signature_top_left_pt(
    click_x: float,
    click_y: float,
    display_width: int,
    display_height: int,
    rendered_width: int,
    rendered_height: int,
    sig_width_pt: float,
    sig_height_pt: float,
    page_width_pt: float,
    page_height_pt: float,
    dpi: int = 150,
) -> tuple[float, float]:
    rendered_x_px = click_x * (rendered_width / display_width)
    rendered_y_px = click_y * (rendered_height / display_height)
    center_x_pt = px_to_pt(rendered_x_px, dpi)
    center_y_pt = px_to_pt(rendered_y_px, dpi)
    return click_center_to_signature_top_left_pt(
        center_x_pt,
        center_y_pt,
        sig_width_pt,
        sig_height_pt,
        page_width_pt,
        page_height_pt,
    )


if __name__ == "__main__":
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "Internship Application Form", fontsize=20)
    page.insert_text((100, 200), "Full Name: ____________________")
    page.insert_text((100, 300), "Signature: ____________________")
    doc.save("test.pdf")
    doc.close()
    print("test.pdf created!")

    img = Image.new("RGBA", (300, 100), (255, 255, 255, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), "John Doe", fill=(0, 0, 200, 255))
    img.save("signature.png")
    print("signature.png created!")

    doc = load_pdf("test.pdf")
    print(f"Page count: {get_page_count(doc)}")

    areas = find_signature_areas(doc, 0)
    print(f"Signature areas found: {len(areas)}")
    for a in areas:
        print(f"  {a['reason']} -> x={a['x']:.1f}, y={a['y']:.1f}")

    doc.close()

    output = place_signature("test.pdf", 0, 100, 290, "signature.png")
    print(f"Signed PDF saved: {output}")
