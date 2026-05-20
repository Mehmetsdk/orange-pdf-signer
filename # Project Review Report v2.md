# Project Review Report

## Backend First Version Review

The first backend version focuses on PDF processing and signature placement functionality.

The backend starts by loading PDF files.

```python
def load_pdf(pdf_path):
```

This function checks whether the PDF exists before opening it. This improves reliability and prevents invalid file access.

PDF rendering functionality was implemented.

```python
def render_page(doc, page_number):
```

This converts PDF pages into images so they can later be displayed in the interface.

Signature detection was implemented using two approaches.

The first approach searches predefined keywords.

```python
SIGNATURE_KEYWORDS = [
    "signature",
    "imza",
    "sign here"
]
```

The system scans PDF content and tries to identify possible signature locations.

The second approach detects horizontal lines.

```python
page.get_drawings()
```

This allows the system to detect signature lines even if signature keywords are missing.

Signature placement functionality was also implemented.

```python
def place_signature(...)
```

The backend loads the signature image, resizes it, and inserts it into the PDF document.

Coordinate conversion functions were added.

```python
pt_to_px()
px_to_pt()
```

These functions help synchronize PDF coordinates and screen coordinates.

### Working functionality

- PDF loading
- PDF rendering
- Signature keyword detection
- Horizontal line detection
- Signature image insertion
- Coordinate conversion

### Improvement opportunities

- Automatic signature detection may not always find the correct location.
- Placement precision could be improved.

Overall, the first backend version creates a working foundation for PDF signing functionality.

### Recommended improvements

The following improvements may further increase reliability and usability:

- Add JSON output support for detection results to simplify debugging and validation processes.

- Improve signature image resizing behavior using more consistent scaling and DPI conversion methods.

- Add stronger error handling mechanisms and more informative log messages to improve debugging and user feedback.

These improvements may increase placement consistency and improve maintainability for future development.