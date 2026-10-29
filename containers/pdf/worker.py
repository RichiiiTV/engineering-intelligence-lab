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
    result = convert_pdf_bytes(raw, Path("/models"))
    print(
        json.dumps(
            {**result, "isolation": "docker-network-none-readonly-nonroot-v1"}, ensure_ascii=False
        )
    )
