import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/model_manifest.py"
spec = importlib.util.spec_from_file_location("eil_model_manifest", SCRIPT)
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


def model(tmp_path):
    root = tmp_path / "generated-model"
    root.mkdir()
    (root / "config.json").write_text('{"architectures":["GeneratedFixture"]}')
    (root / "tokenizer.json").write_text('{"generated":true}')
    (root / "model.safetensors").write_bytes(b"generated test weights, not an actual model")
    return root


def test_manifest_is_deterministic_relative_and_verifies_all_local_assets(tmp_path, capsys):
    root = model(tmp_path)
    target = tmp_path / "reviewed.json"
    assert manifest.main([str(root), "--output", str(target)]) == 0
    revision = capsys.readouterr().out.strip()
    assert revision == hashlib.sha256(target.read_bytes()).hexdigest()
    assert str(tmp_path) not in target.read_text()
    assert manifest.main([str(root), "--verify", str(target), "--expected-sha256", revision]) == 0
    assert manifest.manifest_bytes(root) == target.read_bytes()
    assert {r["path"] for r in json.loads(target.read_bytes())["files"]} == {
        "config.json",
        "tokenizer.json",
        "model.safetensors",
    }


@pytest.mark.parametrize("change", ["weights", "tokenizer", "added"])
def test_manifest_rejects_changed_or_added_model_assets(tmp_path, change):
    root = model(tmp_path)
    target = tmp_path / "reviewed.json"
    raw = manifest.manifest_bytes(root)
    target.write_bytes(raw)
    revision = hashlib.sha256(raw).hexdigest()
    changed = {
        "weights": "model.safetensors",
        "tokenizer": "tokenizer.json",
        "added": "generation_config.json",
    }[change]
    (root / changed).write_bytes(b"changed/generated")
    with pytest.raises(ValueError, match="differ"):
        manifest.verify(root, target, revision)


def test_manifest_never_follows_embedded_traversal_and_never_overwrites(tmp_path, capsys):
    root = model(tmp_path)
    target = tmp_path / "reviewed.json"
    raw = b'{"schema":"eil-local-model-snapshot-v1","files":[{"path":"../../sensitive"}]}\n'
    target.write_bytes(raw)
    revision = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="differ"):
        manifest.verify(root, target, revision)
    assert manifest.main([str(root), "--output", str(target)]) == 2
    assert target.read_bytes() == raw
    assert "sensitive" not in capsys.readouterr().err
    assert manifest.main([str(root), "--output", str(root / "manifest.json")]) == 2


def test_manifest_rejects_missing_local_tokenizer_or_weights(tmp_path):
    root = model(tmp_path)
    (root / "tokenizer.json").unlink()
    with pytest.raises(ValueError, match="tokenizer"):
        manifest.manifest_bytes(root)
    (root / "tokenizer.json").write_text("{}")
    (root / "model.safetensors").unlink()
    with pytest.raises(ValueError, match="safetensors"):
        manifest.manifest_bytes(root)


def test_hidden_referenced_tokenizer_asset_is_hashed_and_mutation_rejected(tmp_path):
    root = model(tmp_path)
    (root / ".assets").mkdir()
    asset = root / ".assets/tokenizer.1.0.0.json"
    asset.write_text('{"generated":true}')
    (root / "tokenizer_config.json").write_text(
        json.dumps({"fast_tokenizer_files": [".assets/tokenizer.1.0.0.json"]})
    )
    raw = manifest.manifest_bytes(root)
    assert ".assets/tokenizer.1.0.0.json" in {r["path"] for r in json.loads(raw)["files"]}
    target = tmp_path / "reviewed.json"
    target.write_bytes(raw)
    revision = hashlib.sha256(raw).hexdigest()
    asset.write_text('{"generated":"changed"}')
    with pytest.raises(ValueError, match="differ"):
        manifest.verify(root, target, revision)


@pytest.mark.parametrize("reference", ["../outside.json", "/outside.json", "C:/outside.json"])
def test_manifest_rejects_external_tokenizer_references(tmp_path, reference):
    root = model(tmp_path)
    (root / "tokenizer_config.json").write_text(json.dumps({"tokenizer_file": reference}))
    with pytest.raises(ValueError, match="inside the snapshot"):
        manifest.manifest_bytes(root)


def test_manifest_rejects_symlinked_assets_or_root(tmp_path):
    root = model(tmp_path)
    link = tmp_path / "linked-model"
    try:
        link.symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit creating symlinks")
    with pytest.raises(ValueError, match="symlink"):
        manifest.snapshot(link)
    (root / "extra.json").symlink_to(root / "config.json")
    with pytest.raises(ValueError, match="symlink"):
        manifest.manifest_bytes(root)
    output_target = tmp_path / "unexpected-output.json"
    output_link = tmp_path / "linked-output.json"
    output_link.symlink_to(output_target)
    assert manifest.main([str(root), "--output", str(output_link)]) == 2
    assert not output_target.exists()
