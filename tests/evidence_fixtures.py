"""Captured real Docling output keeps ordinary CI offline and model-free."""

from pathlib import Path

from docling_core.types.doc import DoclingDocument

from eil.pdf_ingest import normalize_document

ROOT = Path(__file__).resolve().parents[1]
PDF_BYTES = (ROOT / "output/pdf/synthetic-maintenance-note.pdf").read_bytes()
CSV_BYTES = (ROOT / "data/synthetic_inspection_v1.csv").read_bytes()


def fixture_pdf_parser(content):
    assert content == PDF_BYTES
    document = DoclingDocument.model_validate_json(
        (ROOT / "tests/fixtures/golden-docling.json").read_text(encoding="utf-8")
    )
    return {**normalize_document(document), "parser_version": "2.144.0", "core_version": "2.105.0"}


def golden_case(store, title="Golden case"):
    case = store.create_case(title)
    pdf = store.ingest(case["id"], "maintenance.pdf", PDF_BYTES, pdf_parser=fixture_pdf_parser)
    csv = store.ingest(case["id"], "inspection.csv", CSV_BYTES)
    return case, pdf, csv
