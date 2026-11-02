"""Native launcher smoke checks: no packages, services or HPC jobs are started."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    os.name != "posix" or not shutil.which("bash"), reason="Linux Bash smoke"
)


@pytest.mark.parametrize(
    "name", ["start-workbench.sh", "start-vllm-native.sh", "start-ollama-hpc.sh"]
)
def test_linux_launcher_help_and_unknown_option_fail_closed(name):
    script = ROOT / "scripts" / name
    subprocess.run(["bash", "-n", str(script)], check=True, capture_output=True, timeout=5)
    result = subprocess.run(
        ["bash", str(script), "--help"], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0 and "Usage:" in result.stdout
    invalid = subprocess.run(
        ["bash", str(script), "--unrecognized"], capture_output=True, text=True, timeout=5
    )
    assert invalid.returncode == 2


def test_native_vllm_launcher_rejects_missing_runtime_configuration():
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("EIL_VLLM", "VLLM_"))}
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/start-vllm-native.sh"), "chat", "--check"],
        env=clean,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0 and "EIL_VLLM_PYTHON" in result.stderr


def test_native_vllm_check_verifies_generated_files_without_starting_server(tmp_path):
    model = tmp_path / "generated-model"
    model.mkdir()
    for name in ("config.json", "tokenizer.json", "model.safetensors"):
        (model / name).write_text("generated fixture")
    manifest = tmp_path / "reviewed.json"
    revision = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/model_manifest.py"),
            str(model),
            "--output",
            str(manifest),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()
    cache = tmp_path / "private-cache"
    cache.mkdir(mode=0o700)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("EIL_VLLM", "VLLM_"))}
    env.update(
        EIL_VLLM_PYTHON=sys.executable,
        EIL_VLLM_CACHE_DIR=str(cache),
        EIL_VLLM_MODEL_PATH=str(model),
        EIL_VLLM_MANIFEST=str(manifest),
        EIL_VLLM_MODEL="eil-generated",
        EIL_VLLM_REVISION=revision,
        EIL_VLLM_API_KEY="generated-check-key-not-a-real-credential",
        EIL_VLLM_TOOL_CALL_PARSER="qwen3_xml",
    )
    command = ["bash", str(ROOT / "scripts/start-vllm-native.sh"), "chat", "--check"]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0 and "no service started" in result.stdout
    assert env["EIL_VLLM_API_KEY"] not in result.stdout + result.stderr
    for length in ("0", "8193", "1; touch forbidden", "-1"):
        rejected = subprocess.run(
            command,
            env=env | {"EIL_VLLM_MAX_MODEL_LEN": length},
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert rejected.returncode == 2 and "1 through 8192" in rejected.stderr
    env.update(
        EIL_VLLM_EMBEDDING_MODEL_PATH=str(model),
        EIL_VLLM_EMBEDDING_MANIFEST=str(manifest),
        EIL_VLLM_EMBEDDING_MODEL="eil-generated-embed",
        EIL_VLLM_EMBEDDING_REVISION=revision,
        EIL_VLLM_EMBEDDING_MAX_MODEL_LEN="512",
    )
    embedding_command = ["bash", str(ROOT / "scripts/start-vllm-native.sh"), "embedding", "--check"]
    valid = subprocess.run(embedding_command, env=env, capture_output=True, text=True, timeout=5)
    assert valid.returncode == 0
    rejected = subprocess.run(
        embedding_command,
        env=env | {"EIL_VLLM_EMBEDDING_MAX_MODEL_LEN": "8193"},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert rejected.returncode == 2
    # A generated fake CLI exercises actual argv assembly, never a GPU engine.
    engine = tmp_path / "fake-engine"
    for package in ("vllm", "vllm/entrypoints", "vllm/entrypoints/cli"):
        folder = engine / package
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "__init__.py").write_text("")
    (engine / "vllm/entrypoints/cli/main.py").write_text(
        "import json,sys\nprint(json.dumps(sys.argv[1:]))\n"
    )
    metadata = engine / "vllm-0.32.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: vllm\nVersion: 0.32.0\n")
    launch_env = env | {
        "PYTHONPATH": str(engine),
        "EIL_VLLM_DTYPE": "bfloat16",
        "EIL_VLLM_MAX_NUM_SEQS": "2",
        "EIL_VLLM_VISION": "0",
    }
    launched = subprocess.run(
        command[:-1], env=launch_env, capture_output=True, text=True, timeout=5
    )
    assert launched.returncode == 0, launched.stderr
    args = json.loads(launched.stdout.splitlines()[-1])
    assert args[args.index("--dtype") + 1] == "bfloat16"
    assert args[args.index("--max-num-seqs") + 1] == "2"
    assert "--language-model-only" in args
    assert env["EIL_VLLM_API_KEY"] not in launched.stdout + launched.stderr
    launched = subprocess.run(
        command[:-1],
        env=launch_env | {"EIL_VLLM_VISION": "1"},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert launched.returncode == 0
    args = json.loads(launched.stdout.splitlines()[-1])
    assert "--language-model-only" not in args
    assert json.loads(args[args.index("--limit-mm-per-prompt") + 1]) == {
        "image": 1,
        "video": 0,
        "audio": 0,
    }
    for setting in ({"EIL_VLLM_DTYPE": "fp8"}, {"EIL_VLLM_MAX_NUM_SEQS": "0"}):
        rejected = subprocess.run(
            command, env=env | setting, capture_output=True, text=True, timeout=5
        )
        assert rejected.returncode == 2
    cache.chmod(0o755)
    rejected = subprocess.run(command, env=env, capture_output=True, text=True, timeout=5)
    assert rejected.returncode != 0 and "no group/other permissions" in rejected.stderr


def test_hpc_ollama_wrapper_fixes_binding_and_preserves_slurm_gpu_visibility(tmp_path):
    binary = tmp_path / "ollama"
    binary.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" "$OLLAMA_HOST" "$OLLAMA_NUM_PARALLEL" '
        '"$CUDA_VISIBLE_DEVICES" "$OLLAMA_NO_CLOUD"\n'
    )
    binary.chmod(0o700)
    model_dir = tmp_path / "models"
    model_dir.mkdir(mode=0o700)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OLLAMA_", "EIL_OLLAMA"))}
    env.update(
        PATH=str(tmp_path) + os.pathsep + env["PATH"],
        OLLAMA_MODELS=str(model_dir),
        OLLAMA_HOST="0.0.0.0:9999",
        CUDA_VISIBLE_DEVICES="2,3",
    )
    command = ["bash", str(ROOT / "scripts/start-ollama-hpc.sh")]
    checked = subprocess.run(
        command + ["--check"], env=env, capture_output=True, text=True, timeout=5
    )
    assert checked.returncode == 0 and "no service started" in checked.stdout
    started = subprocess.run(command, env=env, capture_output=True, text=True, timeout=5)
    assert started.returncode == 0
    assert started.stdout.splitlines() == ["serve", "127.0.0.1:11435", "1", "2,3", "1"]
    bad_port = subprocess.run(
        command + ["--check"],
        env=env | {"EIL_OLLAMA_PORT": "0;id"},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert bad_port.returncode == 2
    model_dir.chmod(0o755)
    rejected = subprocess.run(
        command + ["--check"], env=env, capture_output=True, text=True, timeout=5
    )
    assert rejected.returncode == 2 and "mode 0700" in rejected.stderr
