"""Operator-only materialized model snapshot manifest; no downloads or code execution."""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

MAX_FILES = 10000
MAX_MANIFEST_BYTES = 4 * 1024**2
SCHEMA = "eil-local-model-snapshot-v1"
MAX_CONFIG_BYTES = 16 * 1024**2
TOKENIZER_FILE_KEYS = frozenset(
    {
        "tokenizer_file",
        "vocab_file",
        "merges_file",
        "spm_file",
        "sentencepiece_model_file",
        "tokenizer_model_file",
        "added_tokens_file",
        "special_tokens_map_file",
        "tokenizer_config_file",
        "chat_template_file",
    }
)


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024**2):
            digest.update(block)
    return digest.hexdigest()


def checked_reference(root, config, value):
    """Validate known filename references without ever following an outside path."""
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ValueError("Model asset filename references must be nonempty local strings")
    if (
        PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).drive
        or ".." in PurePosixPath(value.replace("\\", "/")).parts
        or "\\" in value
        or ":" in value
    ):
        raise ValueError("Model asset filename references must stay inside the snapshot")
    candidate = config.parent / value
    # Snapshot enumeration rejects symlinks, and this containment check is also
    # required before stat/read of an explicitly referenced asset.
    if not candidate.resolve().is_relative_to(root):
        raise ValueError("Model asset filename references must stay inside the snapshot")
    if not candidate.is_file():
        raise ValueError("A referenced local model asset is missing")


def validate_references(root, paths):
    for path in paths:
        if path.name != "tokenizer_config.json" and not path.name.endswith(".index.json"):
            continue
        if path.stat().st_size > MAX_CONFIG_BYTES:
            raise ValueError("Model filename configuration exceeds its bounded size")
        try:
            config = json.loads(path.read_bytes())
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Model filename configuration must be valid JSON") from exc
        if not isinstance(config, dict):
            raise ValueError("Model filename configuration must be a JSON object")
        if path.name == "tokenizer_config.json":
            for key in TOKENIZER_FILE_KEYS:
                if config.get(key) is not None:
                    checked_reference(root, path, config[key])
            if "fast_tokenizer_files" in config:
                values = config["fast_tokenizer_files"]
                if not isinstance(values, list):
                    raise ValueError("Versioned tokenizer filenames must be a list")
                for value in values:
                    checked_reference(root, path, value)
        if "weight_map" in config:
            weights = config["weight_map"]
            if not isinstance(weights, dict):
                raise ValueError("Model weight_map must be a JSON object")
            for value in weights.values():
                checked_reference(root, path, value)


def snapshot(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Use an existing materialized local model directory, not a symlink")
    root = directory.resolve(strict=True)
    files = []
    paths = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValueError("Model snapshots must not contain symlinked files or directories")
        if not path.is_file():
            if not path.is_dir():
                raise ValueError("Model snapshot contains a non-regular file")
            continue
        if any(ord(char) < 32 for char in str(relative)):
            raise ValueError("Model snapshot contains a control character in a filename")
        files.append(
            {"path": relative.as_posix(), "size": path.stat().st_size, "sha256": file_digest(path)}
        )
        paths.append(path)
        if len(files) > MAX_FILES:
            raise ValueError("Model snapshot exceeds the 10,000-file limit")
    names = {row["path"] for row in files}
    if "config.json" not in names or not any(name.endswith(".safetensors") for name in names):
        raise ValueError("A model config and local safetensors weights are required")
    if not any(name in names for name in ("tokenizer.json", "tokenizer.model", "vocab.json")):
        raise ValueError("A local tokenizer is required")
    validate_references(root, paths)
    return {"schema": SCHEMA, "files": files}


def manifest_bytes(directory):
    return (json.dumps(snapshot(directory), sort_keys=True, separators=(",", ":")) + "\n").encode()


def verify(directory, manifest, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Expected a lowercase manifest SHA256")
    manifest = Path(manifest)
    if (
        manifest.is_symlink()
        or not manifest.is_file()
        or manifest.stat().st_size > MAX_MANIFEST_BYTES
    ):
        raise ValueError("Use a regular bounded manifest file")
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Manifest hash does not match the reviewed revision")
    # Recompute from local files; never use manifest paths for filesystem access.
    # Exact canonical bytes also reject traversal entries, duplicate names and extras.
    if raw != manifest_bytes(directory):
        raise ValueError("Local model/tokenizer bytes differ from the reviewed snapshot")
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--output", type=Path, help="Create a fresh manifest outside the model directory"
    )
    group.add_argument("--verify", type=Path, help="Verify an existing reviewed manifest")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args(argv)
    try:
        if args.verify is not None:
            revision = verify(args.directory, args.verify, args.expected_sha256 or "")
        else:
            if args.expected_sha256:
                raise ValueError("--expected-sha256 requires --verify")
            root = args.directory.resolve(strict=True)
            if args.output.is_symlink():
                raise ValueError("Manifest output must not be a symlink")
            output = args.output.resolve()
            if output.is_relative_to(root):
                raise ValueError("Keep the manifest outside the model directory")
            raw = manifest_bytes(args.directory)
            if len(raw) > MAX_MANIFEST_BYTES:
                raise ValueError("Manifest exceeds its size limit")
            # Parent directories must already exist with operator-selected permissions.
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
            revision = hashlib.sha256(raw).hexdigest()
        print(revision)
        return 0
    except (OSError, ValueError) as exc:
        # Avoid echoing host model paths or system-error payloads to shared logs.
        print(
            str(exc) if isinstance(exc, ValueError) else "Local snapshot file operation failed",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
