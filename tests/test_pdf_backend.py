from pathlib import Path

import fitz
from PIL import Image

from pdf_backend import (
    apply_opacity,
    clamp_signature_position,
    click_center_to_signature_top_left_pt,
    place_signature_image,
    process_signature_image,
    remove_light_background_pillow,
    resize_signature_to_box,
    trim_transparent_edges,
)


def _white_rgba(w=40, h=40):
    return Image.new("RGBA", (w, h), (255, 255, 255, 255))


def _ink_on_white():
    img = Image.new("RGBA", (60, 40), (255, 255, 255, 255))
    for x in range(10, 50):
        for y in range(15, 25):
            img.putpixel((x, y), (0, 0, 0, 255))
    return img


def test_remove_light_background_pillow_makes_white_transparent():
    img = _white_rgba()
    out = remove_light_background_pillow(img, white_threshold=245)
    assert out.mode == "RGBA"
    assert out.getpixel((20, 20))[3] == 0


def test_remove_light_background_keeps_ink():
    img = _ink_on_white()
    out = remove_light_background_pillow(img, white_threshold=245)
    assert out.getpixel((20, 20))[3] == 255


def test_apply_opacity_changes_alpha():
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 200))
    out = apply_opacity(img, 0.5)
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 100


def test_trim_transparent_edges_crops_border():
    img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    for x in range(20, 30):
        for y in range(20, 30):
            img.putpixel((x, y), (255, 0, 0, 255))
    out = trim_transparent_edges(img)
    assert out.size == (10, 10)


def test_resize_signature_to_box_exact_size():
    img = Image.new("RGBA", (80, 40), (0, 0, 255, 255))
    out = resize_signature_to_box(img, 100, 60, preserve_aspect_ratio=True)
    assert out.size == (100, 60)
    assert out.mode == "RGBA"


def test_resize_signature_to_box_preserves_aspect_with_padding():
    img = Image.new("RGBA", (80, 20), (255, 0, 0, 255))
    out = resize_signature_to_box(img, 100, 60, preserve_aspect_ratio=True)
    assert out.size == (100, 60)
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((50, 30))[0:3] == (255, 0, 0)


def test_place_signature_image_preserves_aspect_ratio_in_pdf(tmp_path: Path):
    pdf_path = tmp_path / "input.pdf"
    output_path = tmp_path / "signed.pdf"

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20, 20), "Test PDF")
    doc.save(str(pdf_path))
    doc.close()

    sig = Image.new("RGBA", (80, 20), (255, 0, 0, 255))
    place_signature_image(
        str(pdf_path),
        0,
        50,
        80,
        sig,
        width=100,
        height=60,
        preserve_aspect_ratio=True,
        output_path=str(output_path),
    )

    signed = fitz.open(str(output_path))
    rendered = signed[0].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    preview = Image.frombytes("RGB", [rendered.width, rendered.height], rendered.samples)

    assert preview.getpixel((55, 85)) == (255, 0, 0)
    assert preview.getpixel((95, 85)) != (255, 0, 0)
    signed.close()


def test_click_center_to_signature_top_left_subtracts_half_size():
    x_pt, y_pt = click_center_to_signature_top_left_pt(
        100.0, 100.0, 40.0, 20.0, 500.0, 700.0
    )
    assert x_pt == 80.0
    assert y_pt == 90.0


def test_clamp_signature_position_negative_to_zero():
    x_pt, y_pt = clamp_signature_position(-10.0, -5.0, 500.0, 700.0, 40.0, 20.0)
    assert x_pt == 0.0
    assert y_pt == 0.0


def test_clamp_signature_position_keeps_signature_inside_page():
    x_pt, y_pt = clamp_signature_position(480.0, 690.0, 500.0, 700.0, 40.0, 20.0)
    assert x_pt == 460.0
    assert y_pt == 680.0


def test_click_center_clamps_when_signature_would_overflow():
    x_pt, y_pt = click_center_to_signature_top_left_pt(
        490.0, 690.0, 40.0, 20.0, 500.0, 700.0
    )
    assert x_pt == 460.0
    assert y_pt == 680.0


def test_process_signature_image_returns_rgba_without_rembg():
    img = _ink_on_white()
    out = process_signature_image(
        img,
        remove_background=True,
        use_rembg=False,
        white_threshold=245,
        opacity=0.9,
        rotation_degrees=0,
        trim_transparent=False,
    )
    assert out.mode == "RGBA"
    assert out.size[0] > 0
