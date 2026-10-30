"""Container entrypoint: bounded stdin PDF, normalized JSON stdout, no host paths."""

import json
import sys
from pathlib import Path

from eil.pdf_ingest import MAX_PDF_BYTES, convert_pdf_bytes

if "--self-test" in sys.argv:
    import os
    import socket

    network_denied = False
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=1)
    except OSError:
        network_denied = True
    write_denied = False
    try:
        Path("/app/forbidden").write_text("untrusted write")
    except OSError:
        write_denied = True
    controls = {
        name: Path("/sys/fs/cgroup/" + name).read_text().strip()
        for name in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")
    }
    status = Path("/proc/self/status").read_text().splitlines()
    controls.update(
        {
            line.split(":")[0]: line.split(":")[1].strip()
            for line in status
            if line.startswith(("CapEff:", "NoNewPrivs:", "Seccomp:"))
        }
    )
    print(
        json.dumps(
            {
                "uid": os.getuid(),
                "network_denied": network_denied,
                "root_read_only": write_denied,
                "models_present": Path("/models").is_dir(),
                "controls": controls,
            }
        )
    )
else:
    raw = sys.stdin.buffer.read(MAX_PDF_BYTES + 1)
    if not raw.startswith(b"%PDF-") or len(raw) > MAX_PDF_BYTES:
        raise ValueError("Invalid or oversized PDF")
    page_range = None
    if "--pages" in sys.argv:
        if len(sys.argv) != 4 or sys.argv[1] != "--pages":
            raise ValueError("Invalid batch arguments")
        start, end = map(int, sys.argv[2:])
        if not 1 <= start <= end <= 200 or end - start >= 20:
            raise ValueError("Invalid page batch")
        page_range = (start, end)
    result = convert_pdf_bytes(
        raw, Path("/models"), page_range=page_range, max_pages=200 if page_range else 20
    )
    print(
        json.dumps(
            {**result, "isolation": "docker-network-none-readonly-nonroot-v1"}, ensure_ascii=False
        )
    )
