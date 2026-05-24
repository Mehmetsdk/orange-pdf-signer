import fitz  # PyMuPDF
from PIL import Image
import io
import os


SIGNATURE_KEYWORDS = [
    "signature", "imza", "sign here", "buraya imza",
    "authorized signature", "yetkili imza", "imzası"
]

    return output_path

def pt_to_px(pt_value: float, dpi: int = 150) -> float:
    return pt_value * (dpi / 72)

def px_to_pt(px_value: float, dpi: int = 150) -> float:
    return px_value * (72 / dpi)

