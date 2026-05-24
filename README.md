# Orange PDF Signer

A Streamlit-based PDF signing application that allows users to upload a PDF, upload a signature image, preview the document, and place the signature either automatically or manually.

The project focuses on making PDF signing simple and visual. Instead of forcing users to guess X/Y coordinates, the app supports mouse-based manual placement on a clickable PDF preview. Users can still fine-tune the final position with numeric coordinate inputs.

---

## Features

### PDF Upload

Users can upload a PDF file directly from the Streamlit interface.

The app renders the selected PDF page as an image preview so the user can see where the signature will be placed before exporting the final signed document.

---

### Signature Image Upload

Users can upload a signature image file.

Supported image formats depend on Pillow support, but common formats such as PNG and JPG/JPEG are expected to work.

The app processes the uploaded signature before inserting it into the PDF.

---

### Manual Mouse-Based Signature Placement

The main feature of this version is visual manual placement.

Instead of only entering X/Y coordinates, users can click directly on the PDF preview to place the signature.

The clicked point is treated as the center of the signature. The app then converts the clicked preview coordinates into real PDF coordinates and updates the signature position.

This makes the manual signing flow much easier:

1. Upload a PDF.
2. Upload a signature image.
3. Select manual placement.
4. Click on the PDF preview.
5. Fine-tune with X/Y controls if needed.
6. Download the signed PDF.

---

### X/Y Coordinate Fine-Tuning

Manual X/Y coordinate inputs are still available.

This is useful when the user wants more precise control after clicking on the preview.

The coordinate inputs act as a fallback and fine-tuning mechanism.

---

### Automatic Signature Detection

The app also includes an automatic placement mode.

The backend can search for likely signature areas using simple detection logic such as signature-related text or visual placement hints.

This mode is useful when the PDF already contains clear signing areas.

Manual mode is still available when automatic detection is not accurate enough.

---

### Signature Styling Options

The app includes helper logic for preparing the signature image before inserting it into the PDF.

Depending on the current UI options and backend functions, the signature can support:

- Resizing
- Opacity adjustment
- Rotation
- Transparent background handling
- Trimming unnecessary transparent margins
- Placement inside the PDF page bounds

These options help make the inserted signature look cleaner and more natural.

---

### PDF Preview

Before downloading the final PDF, the user can preview the selected page with the signature applied.

The preview is important because PDF coordinate systems and screen preview sizes are different.

The app handles the conversion between:

- displayed preview pixels
- internally rendered image pixels
- PDF points

This helps keep the preview position and the exported PDF position consistent.

---

### Export Signed PDF

After placement is confirmed, the app generates a signed PDF file.

The final output keeps the original PDF content and inserts the processed signature image at the selected location.

The user can then download the signed document from the Streamlit interface.

---

## Tech Stack

The project uses:

- Python
- Streamlit
- PyMuPDF
- Pillow
- streamlit-image-coordinates
- pytest

Optional or image-processing-related dependencies may also be included depending on the current implementation.

---

## Project Structure

orange-pdf-signer/
│
├── app.py
│   └── Streamlit user interface.
│       Handles file upload, preview, manual placement UI, and download flow.
│
├── pdf_backend.py
│   └── Backend PDF and image-processing logic.
│       Handles PDF rendering, signature processing, coordinate conversion,
│       placement, and signed PDF generation.
│
├── requirements.txt
│   └── Python dependencies required to run the app and tests.
│
├── tests/
│   └── Backend tests for helper functions and placement logic.
│
├── examples/
│   └── Example/demo scripts from the original repository.
│
├── PR_NOTE.md
│   └── Project or pull request notes.
│
├── LICENSE
│   └── License file.
│
└── .gitignore
    └── Prevents local environment/cache files from being committed.
Installation
1. Clone the repository
git clone https://github.com/Mehmetsdk/orange-pdf-signer.git
cd orange-pdf-signer

If you are working on a feature branch:

git checkout -b your-branch-name

Example:

git checkout -b CanKOKSAL-manual-signature-placement
2. Create a virtual environment

On Windows PowerShell:

python -m venv .venv
.\.venv\Scripts\Activate.ps1

If PowerShell blocks activation, run:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Then activate again:

.\.venv\Scripts\Activate.ps1

On macOS/Linux:

python -m venv .venv
source .venv/bin/activate
3. Install dependencies
pip install -r requirements.txt

If needed, upgrade pip first:

python -m pip install --upgrade pip
pip install -r requirements.txt
Running the Application

Start the Streamlit app:

streamlit run app.py

If the streamlit command is not recognized:

python -m streamlit run app.py

After running the command, Streamlit will show a local URL in the terminal.

Usually it looks like:

http://localhost:8501

Open that link in your browser.

How to Use
Basic Signing Flow
Start the app.
Upload a PDF file.
Upload a signature image.
Select the PDF page you want to preview/sign.
Choose the placement mode.
Adjust signature size, opacity, rotation, or other available settings.
Preview the result.
Download the signed PDF.
Manual Placement Flow

Manual placement is designed for visual control.

Choose manual placement mode.
Click directly on the PDF preview.
The app places the signature around the clicked point.
Use X/Y coordinate inputs for small adjustments.
Download the final signed PDF.

The clicked point is interpreted as the center of the signature.

This means that if the user clicks the middle of a signature box, the signature should be centered around that location.

Automatic Placement Flow

Automatic placement attempts to find a likely signing area in the document.

This may rely on text or visual cues inside the PDF.

Examples of possible signing hints:

“Signature”
“Sign here”
“Signed by”
Signature lines
Other signing-related markers

Automatic detection may not always be perfect, especially on complex PDF layouts. In those cases, manual placement should be used.

Coordinate System Explanation

PDF placement can be confusing because the app deals with several coordinate systems.

The main systems are:

1. Displayed Preview Coordinates

These are the coordinates from the image shown in the browser.

The preview may be resized for display.

For example, the actual rendered PDF page may be much larger than the image shown in Streamlit.

2. Rendered Image Pixel Coordinates

The PDF page is rendered internally as an image.

This rendered image has its own pixel dimensions.

The displayed preview click must first be scaled back to the rendered image size.

3. PDF Point Coordinates

PDFs use points.

One PDF point is equal to 1/72 inch.

The final signature must be placed using PDF point coordinates, not browser pixels.

Coordinate Conversion Flow

When the user clicks the preview:

display click position
        ↓
scaled to rendered image pixels
        ↓
converted to PDF points
        ↓
adjusted so clicked point becomes signature center
        ↓
clamped inside page boundaries
        ↓
used for preview and final PDF export

This conversion is necessary so that the preview and the downloaded signed PDF match.

Signature Bounds Handling

The signature should not be placed outside the PDF page.

The app should clamp placement values so that:

x >= 0
y >= 0
x + signature_width <= page_width
y + signature_height <= page_height

This prevents the signature from disappearing outside the visible document area.

Testing

Run the test suite:

pytest -q

If pytest is not recognized:

python -m pytest -q

Tests are used to verify backend behavior such as:

coordinate conversion
placement calculations
signature boundary clamping
image/PDF helper functions
Manual Testing Checklist

Before opening or merging a pull request, test the app manually.

App Startup
 pip install -r requirements.txt works.
 streamlit run app.py starts the app.
 The app opens in the browser.
Upload Flow
 A PDF can be uploaded.
 A signature image can be uploaded.
 The selected PDF page is previewed.
Manual Placement
 Manual mode is available.
 Clicking the PDF preview moves the signature.
 The clicked point behaves like the center of the signature.
 X/Y inputs still work.
 The signature cannot be moved outside the page.
 The preview updates correctly after placement changes.
Export
 The signed PDF can be downloaded.
 The downloaded PDF matches the preview placement.
 The original PDF content is preserved.
 The signature appears clearly.
Automatic Placement
 Auto-detect mode still works.
 Manual mode still works even if auto-detect fails or is inaccurate.
Development Notes
Do not commit local environment files

The following should not be committed:

.venv/
__pycache__/
.pytest_cache/
*.pyc

These are local development/cache files and should stay out of Git.

Recommended Git Workflow

Create a branch for your feature:

git checkout -b CanKOKSAL-manual-signature-placement

After making changes:

git status
git add app.py pdf_backend.py requirements.txt tests/ .gitignore README.md
git commit -m "Add mouse-based manual signature placement"
git push -u origin CanKOKSAL-manual-signature-placement

Then open a pull request on GitHub.

Pull Request Notes

A good pull request description should explain:

what feature was added
why it was needed
which files were changed
how reviewers can test it
any important coordinate or placement details

For this project, reviewers should especially check that:

preview placement matches final PDF placement
click-to-place behavior works correctly
X/Y fine-tuning still works
automatic placement was not broken
Troubleshooting
streamlit command not found

Use:

python -m streamlit run app.py
PowerShell cannot activate virtual environment

Run:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Then:

.\.venv\Scripts\Activate.ps1
Package installation fails

Upgrade pip:

python -m pip install --upgrade pip
pip install -r requirements.txt

If an image-processing dependency causes issues, check whether the app can still run with the core dependencies installed.

Signature appears in a different place in the downloaded PDF

This usually means there is a coordinate conversion mismatch.

Check the conversion between:

display preview pixels
rendered image pixels
PDF points

Also verify that the preview width and rendered image dimensions are used correctly when converting click coordinates.

Signature goes outside the page

Check the clamping logic.

The final X/Y values should be limited so the signature rectangle stays inside the PDF page boundaries.

Future Improvements

Possible improvements for later versions:

Drag-and-drop signature movement instead of click-to-place only
Multiple signatures per PDF
Support for initials
Text/date stamping
Multi-page signing
Better automatic detection
Signature presets
Save recent signature settings
Add undo/reset placement controls
Improved UI layout and preview zoom
More detailed test coverage for PDF edge cases
License

See the LICENSE file for project license information.

