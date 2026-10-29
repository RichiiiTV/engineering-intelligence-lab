"""Explicit operator smoke check through the real container; not part of offline CI."""

import json
from pathlib import Path

from eil.isolated_pdf import convert
from eil.settings import ROOT

probe = convert(b"", self_test=True)
assert probe["uid"] == 65532
assert probe["network_denied"] and probe["root_read_only"] and probe["models_present"]
assert probe["controls"] == {
    "memory.max": "2147483648",
    "memory.swap.max": "0",
    "cpu.max": "200000 100000",
    "pids.max": "128",
    "CapEff": "0000000000000000",
    "NoNewPrivs": "1",
    "Seccomp": "2",
}
result = convert((ROOT / "output/pdf/synthetic-maintenance-note.pdf").read_bytes())
assert (
    result["page_count"] == 2 and result["isolation"] == "docker-network-none-readonly-nonroot-v1"
)
assert any(
    c["kind"] == "table" and "2400" in c["text"] and "800" in c["text"] for c in result["chunks"]
)
output = ROOT / "reports/pdf-isolation"
output.mkdir(parents=True, exist_ok=True)
(output / "probe.json").write_text(json.dumps(probe, indent=2))
(output / "golden.json").write_text(json.dumps(result, indent=2))
print(
    json.dumps(
        {
            "passed": True,
            "pages": result["page_count"],
            "chunks": len(result["chunks"]),
            "artifacts": str(Path(output)),
        }
    )
)
