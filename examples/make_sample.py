from PIL import Image, ImageDraw
import fitz
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def make_pdf(path: str):
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), "Please sign here:", fontsize=16)
        shape = page.new_shape()
        shape.draw_line((150, 200), (450, 200))
        shape.finish(color=(0, 0, 0), width=1)
        shape.commit()
        doc.save(path)
    finally:
        doc.close()


def make_signature(path: str):
    img = Image.new("RGBA", (300, 100), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.line((20, 60, 80, 30, 140, 70, 200, 30, 260, 60), fill=(0, 0, 0), width=6)
    img.save(path)


if __name__ == '__main__':
    sample_pdf = os.path.join(BASE_DIR, 'sample.pdf')
    signature_png = os.path.join(BASE_DIR, 'signature.png')
    make_pdf(sample_pdf)
    make_signature(signature_png)
    print(f'Created {sample_pdf} and {signature_png}')
