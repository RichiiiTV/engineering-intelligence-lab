"""Capture real offline Docling normalization and render each owned fixture page."""

import hashlib
import json
from pathlib import Path

from eil.pdf_ingest import convert_pdf_bytes

ROOT = Path(__file__).resolve().parents[1]


def main():
    import pypdfium2 as pdfium

    output = ROOT / "data/benchmarks/eil-v1"
    rendered = ROOT / "tmp/pdfs/m5"
    rendered.mkdir(parents=True, exist_ok=True)
    metadata = {}
    for key in ("known-cause", "ambiguous", "injection"):
        path = ROOT / f"output/pdf/m5-{key}.pdf"
        raw = path.read_bytes()
        normalized = output / f"{key}.docling.json"
        normalized.write_text(
            json.dumps(convert_pdf_bytes(raw), indent=2), encoding="utf-8", newline="\n"
        )
        metadata[key] = {
            "pdf_sha256": hashlib.sha256(raw).hexdigest(),
            "csv_sha256": hashlib.sha256((output / f"{key}.csv").read_bytes()).hexdigest(),
            "normalized_sha256": hashlib.sha256(normalized.read_bytes()).hexdigest(),
        }
        pdf = pdfium.PdfDocument(raw)
        for n in range(len(pdf)):
            pdf[n].render(scale=1).to_pil().save(rendered / f"{key}-{n + 1}.png")
        pdf.close()
        print(key, "captured", flush=True)
    (output / "hashes.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
