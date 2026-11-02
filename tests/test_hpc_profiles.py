import importlib.util
import json
import shlex
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/hpc_profiles.py"
spec = importlib.util.spec_from_file_location("eil_hpc_profiles", SCRIPT)
profiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profiles)


@pytest.mark.parametrize("name", profiles.PROFILES)
def test_profiles_generate_conservative_templates_without_starting_or_downloading(name, capsys):
    assert profiles.main([name]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["plan_only"] and not plan["hardware_validated"]
    env = plan["settings"]
    assert env["EIL_VLLM_DTYPE"] == "bfloat16"
    assert env["EIL_VLLM_EMBEDDING_DTYPE"] == "bfloat16"
    assert env["EIL_VLLM_MAX_MODEL_LEN"] == "8192"
    assert int(env["EIL_VLLM_TENSOR_PARALLEL_SIZE"]) == profiles.PROFILES[name]["count"]
    assert (
        float(env["EIL_VLLM_GPU_MEMORY_UTILIZATION"])
        + float(env["EIL_VLLM_EMBEDDING_GPU_MEMORY_UTILIZATION"])
        <= 0.95
    )
    assert env["EIL_VLLM_EMBEDDING_INPUT_FORMAT"] == "qwen3"
    assert env["EIL_VLLM_VISION"] == "0"
    assert not any(k.endswith("API_KEY") for k in env)
    assert profiles.main([name, "--format", "env"]) == 0
    lines = capsys.readouterr().out.splitlines()
    parsed = dict(shlex.split(line)[0].split("=", 1) for line in lines if not line.startswith("#"))
    assert parsed == env


def test_legacy_ollama_route_has_explicit_older_text_models(capsys):
    profiles.main(["a100-40gb", "--backend", "ollama"])
    result = json.loads(capsys.readouterr().out)
    assert result["settings"]["EIL_OLLAMA_MODEL"] == "qwen3:14b-q8_0"
    assert "3.5" not in result["upstream_chat"]
    assert result["upstream_embedding"] == "embeddinggemma:300m"


def test_slurm_gpu_selection_checks_allocation_without_reassigning_devices(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "2,3,4,5")
    monkeypatch.setenv("EIL_VLLM_CHAT_CUDA_VISIBLE_DEVICES", "2,3,4,5")
    monkeypatch.setenv("EIL_VLLM_EMBEDDING_CUDA_VISIBLE_DEVICES", "5")
    monkeypatch.setenv("EIL_VLLM_TENSOR_PARALLEL_SIZE", "4")
    monkeypatch.setenv("EIL_VLLM_EMBEDDING_TENSOR_PARALLEL_SIZE", "1")
    profiles.validate_allocation()
    for key, value in (
        ("EIL_VLLM_CHAT_CUDA_VISIBLE_DEVICES", "0,1,2,3"),
        ("EIL_VLLM_CHAT_CUDA_VISIBLE_DEVICES", "2,3"),
        ("EIL_VLLM_CHAT_CUDA_VISIBLE_DEVICES", "2,2,4,5"),
        ("EIL_VLLM_EMBEDDING_CUDA_VISIBLE_DEVICES", "MIG-generated-fixture"),
    ):
        with monkeypatch.context() as patch:
            patch.setenv(key, value)
            with pytest.raises(ValueError):
                profiles.validate_allocation()
