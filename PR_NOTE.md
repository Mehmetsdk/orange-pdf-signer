This pull request updates the PDF backend processing logic and adds a
small demo script to visualize detected signature areas.

What was added

- Improved `find_signature_areas` with word-based, case-insensitive
  keyword detection and horizontal-line detection.
- Merging of overlapping detection boxes to reduce duplicates.
- CLI helpers and JSON output for detection results.
- `examples/demo_detect.py` to render a page and draw detection boxes.

Notes

- Resolved a merge conflict with `origin/main` by keeping the improved
  backend implementation (merge performed locally and pushed).
- To test locally, run `python examples/demo_detect.py <pdf> <page> out.png`.
