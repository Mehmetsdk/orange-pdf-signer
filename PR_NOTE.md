This pull request prepares the PDF Signer project for handoff to Mehmet.
It keeps the backend as the source of truth for PDF placement and aligns the
UI/demo flow with Mehmet's backend API.

What was added

- Improved backend helpers for signature placement and coordinate handling.
- `place_signature()` is now the integration point for PDF output.
- The Streamlit UI passes the processed signature through Mehmet's backend.
- `examples/demo_detect.py` now draws detected signature areas correctly.
- Regression tests cover image processing and PDF placement behavior.

Notes

- Mehmet owns `pdf_backend.py` and the example scripts.
- Aysel owns `app.py` and the UI wiring.
- Can owns signature-image processing only.
- To test locally, run `python examples/demo_detect.py <pdf> <page> out.png`
  and `python -m pytest -q` if pytest is installed in the environment.
