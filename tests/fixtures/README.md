# M3 generated golden evidence

All content in these fixtures was generated for this project. It contains no company data,
internal logs, third-party manual content or copied instructions for real equipment.

- `output/pdf/synthetic-maintenance-note.pdf` (relative to the repository root) is the
  two-page owned input document. Page 2 contains a synthetic S03 lighting/exposure table.
- `golden-docling.json` is actual `DoclingDocument.export_to_dict()` output captured from
  that PDF using Docling 2.144.0, docling-core 2.105.0, local CPU layout inference and FAST
  TableFormer, with OCR disabled. It is not a hand-authored fake extraction.
- `data/synthetic_inspection_v1.csv` is the existing generated CSV fixture. Its deterministic
  top station is S03, with a 12.5021 percentage-point increase.

The PDF SHA-256 is `db5dd55f9618277e13ab4ea5300a489f7efc20933384a4922c6c60bbe3cc7a5f`.
The CSV SHA-256 is `8238a71955a7418146e370c03b5a2bca6153a81bcf21204a1b405a6d2f3a95bd`.
Both PDF pages were rendered with Poppler and inspected for legibility, clipping and table layout.

Ordinary CI uses the captured Docling document through the real core schema/normalizer,
then real SQLite retrieval, deterministic analytics and a controlled tool-calling graph.
It never downloads models. To verify the native pipeline with prefetched models:

```powershell
uv sync --locked --extra dev --extra documents
uv run --extra documents docling-tools models download layout tableformer --output-dir .eil/docling-models --quiet
uv run --extra documents python scripts/verify_m3_golden.py
```

`generate_golden_pdf.py` is the authoring source. It was run with ReportLab 4.4.9. Regeneration
is authoring work, not part of normal CI; update and visually verify the captured extraction
if the PDF changes. The expected page, table and CSV finding must not be weakened to make
a changed converter pass.
