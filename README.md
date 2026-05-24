# PDF Signer

A web-based PDF signing tool built with Python and Streamlit. Upload a PDF, upload your signature image, and place it precisely — automatically or manually.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red?style=flat-square&logo=streamlit)
![PyMuPDF](https://img.shields.io/badge/PyMuPDF-latest-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## Features

| Feature | Description |
|---|---|
| **Auto-detect** | Scans the PDF for signature keywords and underlines, places the signature automatically |
| **Manual placement** | Click anywhere on the PDF preview to position the signature |
| **Nudge controls** | Fine-tune position with arrow buttons (5pt steps) |
| **Background removal** | Remove white/light backgrounds from the signature image (Pillow fallback or rembg AI) |
| **Opacity & rotation** | Adjust signature transparency and angle |
| **Session persistence** | Last uploaded PDF and signature are restored automatically after page refresh |
| **Live preview** | See exactly how the signed PDF will look before downloading |
| **Download** | Export the signed document as a PDF file |

---

## Tech Stack

- **[Streamlit](https://streamlit.io/)** — Web interface
- **[PyMuPDF (fitz)](https://pymupdf.readthedocs.io/)** — PDF rendering and signature embedding
- **[Pillow](https://pillow.readthedocs.io/)** — Image processing
- **[streamlit-image-coordinates](https://github.com/blackary/streamlit-image-coordinates)** — Click-to-place on PDF preview
- **[rembg](https://github.com/danielgatis/rembg)** *(optional)* — AI-based background removal

---

## Project Structure

```
orange-pdf-signer/
├── app.py                  # Streamlit UI — upload, preview, placement, download
├── pdf_backend.py          # Backend — PDF processing, signature detection & placement
├── requirements.txt        # Python dependencies
├── .streamlit/
│   └── config.toml         # Theme configuration (dark mode)
├── tests/
│   └── test_pdf_backend.py # Unit tests for backend functions
├── examples/
│   ├── demo_detect.py      # Auto-detect demo script
│   ├── demo_place.py       # Placement demo script
│   └── make_sample.py      # Sample PDF generator
└── uploads/                # Local session storage (gitignored)
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Mehmetsdk/orange-pdf-signer.git
cd orange-pdf-signer
```

### 2. Create a virtual environment

**Windows:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> If PowerShell blocks activation: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `rembg` requires an ONNX runtime for AI background removal. If not installed, the app falls back to Pillow-based removal automatically.
> ```bash
> pip install "rembg[cpu]"   # optional — for AI background removal
> ```

### 4. Run the app

```bash
python -m streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## How to Use

### Auto-detect mode
1. Upload your PDF from the sidebar
2. Upload your signature image
3. Select **Auto-detect** placement mode
4. The app finds signature areas (keywords like "Signature:" and underlines)
5. Select the detected area and click **Sign & Download PDF**

### Manual mode
1. Upload your PDF and signature image
2. Select **Manual** placement mode
3. Click on the PDF preview to place the signature
4. Fine-tune with X/Y inputs or nudge buttons (← → ↑ ↓)
5. Click **Sign & Download PDF**

### Signature processing options
| Option | Description |
|---|---|
| Remove background | Makes white/light pixels transparent |
| Opacity | Controls signature transparency (0.10 – 1.00) |
| Rotation | Rotates the signature (−45° to +45°) |
| Trim empty edges | Crops transparent margins automatically |
| Preserve aspect ratio | Keeps the signature proportions when resizing |

---

## Auto-detect Algorithm

The detection engine uses a two-pass approach:

1. **Drawn lines** — Detects horizontal lines from PDF vector drawings
2. **Text underlines** — Detects underscore sequences (`___`) used as signature fields
3. **Keyword matching** — Searches for terms like `Signature`, `Sign here`, `İmza`, etc.

When a keyword and a line are found on the same row, the signature is placed **directly above the line**. Keyword-only matches place the signature to the right of the text.

---

## Coordinate System

PDF coordinates and screen pixels are different. The app handles all conversions internally:

```
Browser click (px)
    → Scaled to rendered image (px)
    → Converted to PDF points (pt)
    → Centered on click position
    → Clamped to page boundaries
    → Applied to preview & exported PDF
```

1 PDF point = 1/72 inch. All placements use PDF points internally.

---

## Running Tests

```bash
pytest -q
```

Tests cover coordinate conversion, placement clamping, signature processing, and PDF helper functions.

---

## Team

| Name | Role |
|---|---|
| **Mehmet** | Backend — PDF processing, auto-detect, coordinate system |
| **Aysel** | UI — Streamlit interface, file validation, user flow |
| **Can** | Signature processing — background removal, opacity, rotation |
| **Sami** | Testing & integration — test suite, QA, merging |

---

## Troubleshooting

**`streamlit` command not found**
```bash
python -m streamlit run app.py
```

**PowerShell won't activate the virtual environment**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**Signature appears in the wrong position in the downloaded PDF**
This is usually a coordinate mismatch. Make sure the preview width (`DISPLAY_WIDTH`) and rendered image dimensions are passed correctly to `display_click_to_signature_top_left_pt()`.

**rembg background removal not working**
Install rembg with CPU support:
```bash
pip install "rembg[cpu]"
```
Without it, the app automatically uses Pillow-based background removal.

---

## License

See [LICENSE](LICENSE) for details.
