"""Optional real Docling golden check; requires prefetched local layout/table models."""

import json
import tempfile
from pathlib import Path

from eil.evidence import EvidenceStore


def main():
    root = Path(__file__).resolve().parents[1]
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="m3-golden-", dir=reports) as directory:
        store = EvidenceStore(directory)
        case = store.create_case("Generated golden evidence")
        pdf = store.ingest(
            case["id"],
            "maintenance.pdf",
            (root / "output/pdf/synthetic-maintenance-note.pdf").read_bytes(),
        )
        csv = store.ingest(
            case["id"], "inspection.csv", (root / "data/synthetic_inspection_v1.csv").read_bytes()
        )
        result = store.compare(case["id"], csv["id"])
        hits = store.search(case["id"], "S03 illumination exposure setpoint", limit=5)["hits"]
        assert result["ranking"][0]["station_id"] == "S03"
        assert result["ranking"][0]["delta_percentage_points"] == 12.5021
        assert hits[0]["page"] == 2
        assert any(h["kind"] == "table" and h["page"] == 2 for h in hits)
        print(
            json.dumps(
                {
                    "passed": True,
                    "parser_version": pdf["parser_version"],
                    "pages": pdf["page_count"],
                    "tables": pdf["table_count"],
                    "retrieved_page": hits[0]["page"],
                    "top_station": "S03",
                    "delta_percentage_points": 12.5021,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
