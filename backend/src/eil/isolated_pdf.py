"""Fixed Docker invocation for the PDF parser. This is never an agent tool."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .settings import DOCLING_ARTIFACTS, ROOT

IMAGE = "eil-pdf-worker:1"
MAX_OUTPUT_BYTES = 16 * 1024 * 1024


class ParserWorkerError(RuntimeError):
    def __init__(self, code, diagnostics):
        super().__init__("Isolated PDF worker rejected the document or exceeded a resource limit")
        self.returncode = code
        self.diagnostics = diagnostics


def docker():
    executable = shutil.which("docker")
    if executable is None and os.name == "nt":
        candidate = (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Docker/Docker/resources/bin/docker.exe"
        )
        if candidate.is_file():
            executable = str(candidate)
    if executable is None:
        raise RuntimeError("Docker Desktop/Linux engine is required for isolated PDF parsing")
    endpoint = (
        "npipe:////./pipe/dockerDesktopLinuxEngine"
        if os.name == "nt"
        else "unix:///var/run/docker.sock"
    )
    return [str(Path(executable).resolve()), "--host", endpoint]


def flags():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def command(name, *, self_test=False, image=IMAGE):
    if image not in {IMAGE, "eil-pdf-worker:2"}:
        raise ValueError("Unapproved parser image")
    base = docker()
    image = subprocess.run(
        [*base, "image", "inspect", image, "--format", "{{.Id}}"],
        capture_output=True,
        timeout=10,
        **flags(),
    )
    image_id = image.stdout.decode("ascii", errors="replace").strip()
    if image.returncode or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise RuntimeError(
            "Build the isolated PDF image: docker build -f containers/pdf/Dockerfile -t eil-pdf-worker:1 ."
        )
    approved = (ROOT / ".eil" / "docling-models").resolve()
    models = DOCLING_ARTIFACTS.resolve()
    if not models.is_dir() or not models.is_relative_to(approved):
        raise RuntimeError(
            "Prefetch PDF model assets into the approved .eil/docling-models directory"
        )
    args = [
        *base,
        "run",
        "--rm",
        "-i",
        "--name",
        name,
        "--network",
        "none",
        "--read-only",
        "--user",
        "65532:65532",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "2g",
        "--memory-swap",
        "2g",
        "--cpus",
        "2",
        "--pids-limit",
        "128",
        "--ulimit",
        "nofile=256:256",
        "--log-driver",
        "none",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=128m,mode=1777",
        "--mount",
        f"type=bind,source={models},target=/models,readonly",
        image_id,
    ]
    if self_test:
        args.append("--self-test")
    return args


def convert(content, *, timeout=120, self_test=False, page_range=None, container_name=None):
    name = container_name or "eil-pdf-" + uuid.uuid4().hex
    if not re.fullmatch(r"eil-(?:pdf|ingest)-[a-f0-9-]{1,50}(?:-p\d+)?", name):
        raise ValueError("Invalid generated parser name")
    args = (
        command(name, self_test=self_test)
        if page_range is None
        else command(name, image="eil-pdf-worker:2")
    )
    if page_range is not None:
        start, end = page_range
        if not 1 <= start <= end <= 200 or end - start >= 20:
            raise ValueError("Invalid page batch")
        args.extend(["--pages", str(start), str(end)])
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **flags(),
    )
    output, errors = bytearray(), bytearray()
    over_limit = threading.Event()

    def read(pipe, buffer, maximum):
        while chunk := pipe.read(65536):
            if len(buffer) + len(chunk) > maximum:
                over_limit.set()
                break
            buffer.extend(chunk)

    def write():
        try:
            process.stdin.write(content)
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    threads = [
        threading.Thread(target=read, args=(process.stdout, output, MAX_OUTPUT_BYTES), daemon=True),
        threading.Thread(target=read, args=(process.stderr, errors, 256 * 1024), daemon=True),
        threading.Thread(target=write, daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        deadline = time.monotonic() + min(timeout, 120)
        while process.poll() is None:
            if over_limit.is_set() or time.monotonic() >= deadline:
                raise RuntimeError("Isolated PDF conversion timed out or exceeded its output limit")
            time.sleep(0.05)
        for thread in threads:
            thread.join(timeout=2)
        if over_limit.is_set():
            raise RuntimeError("Isolated PDF worker exceeded its output limit")
        if process.returncode:
            raise ParserWorkerError(process.returncode, errors.decode("utf-8", errors="replace"))
        result = json.loads(output.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("Invalid isolated parser response")
        return result
    finally:
        if process.poll() is None:
            # Only the generated container for this invocation may be removed.
            subprocess.run(
                [*docker(), "rm", "--force", name], capture_output=True, timeout=10, **flags()
            )
            process.kill()
            process.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=2)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe and not pipe.closed:
                pipe.close()
