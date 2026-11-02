"""Operator-only model/resource plans. Prints configuration; never downloads or submits jobs."""

import argparse
import json
import os
import re
import shlex

PROFILES = {
    "l40s": dict(
        gpu="L40S 48 GB",
        count=1,
        model="Qwen/Qwen3.5-9B",
        slug="qwen3.5-9b",
        tp=1,
        memory="0.75",
        sequences=2,
        ollama="qwen3:14b-q8_0",
    ),
    "a100-40gb": dict(
        gpu="A100 40 GB",
        count=1,
        model="Qwen/Qwen3.5-9B",
        slug="qwen3.5-9b",
        tp=1,
        memory="0.75",
        sequences=2,
        ollama="qwen3:14b-q8_0",
    ),
    "a100-80gb": dict(
        gpu="A100 80 GB",
        count=1,
        model="Qwen/Qwen3.5-27B",
        slug="qwen3.5-27b",
        tp=1,
        memory="0.80",
        sequences=1,
        ollama="qwen3:32b-q8_0",
    ),
    "a100-40gb-x4": dict(
        gpu="A100 40 GB",
        count=4,
        model="Qwen/Qwen3.5-35B-A3B",
        slug="qwen3.5-35b-a3b",
        tp=4,
        memory="0.78",
        sequences=2,
        ollama="qwen3:32b-q8_0",
    ),
}


def configuration(name, backend):
    profile = PROFILES[name]
    if backend == "ollama":
        return {
            "EIL_MODEL_PROVIDER": "ollama",
            "EIL_EMBEDDING_PROVIDER": "ollama",
            "EIL_OLLAMA_BASE_URL": "http://127.0.0.1:11435",
            "EIL_OLLAMA_MODEL": profile["ollama"],
            "EIL_EMBEDDING_MODEL": "embeddinggemma:300m",
            "OLLAMA_SCHED_SPREAD": "1" if profile["count"] > 1 else "0",
        }
    slug = profile["slug"]
    return {
        "EIL_MODEL_PROVIDER": "vllm",
        "EIL_VLLM_BASE_URL": "http://127.0.0.1:8002/v1",
        "EIL_VLLM_MODEL": slug,
        "EIL_VLLM_MODEL_PATH": "/approved/models/" + slug,
        "EIL_VLLM_MANIFEST": "/approved/manifests/" + slug + ".json",
        "EIL_VLLM_REVISION": "REPLACE_WITH_REVIEWED_CHAT_MANIFEST_SHA256",
        "EIL_VLLM_TOOL_CALL_PARSER": "qwen3_coder",
        "EIL_VLLM_VISION": "0",
        "EIL_VLLM_DTYPE": "bfloat16",
        "EIL_VLLM_TENSOR_PARALLEL_SIZE": str(profile["tp"]),
        "EIL_VLLM_GPU_MEMORY_UTILIZATION": profile["memory"],
        "EIL_VLLM_MAX_MODEL_LEN": "8192",
        "EIL_VLLM_MAX_NUM_SEQS": str(profile["sequences"]),
        "EIL_EMBEDDING_PROVIDER": "vllm",
        "EIL_VLLM_EMBEDDING_BASE_URL": "http://127.0.0.1:8003/v1",
        "EIL_VLLM_EMBEDDING_MODEL": "qwen3-embedding-0.6b",
        "EIL_VLLM_EMBEDDING_MODEL_PATH": "/approved/models/qwen3-embedding-0.6b",
        "EIL_VLLM_EMBEDDING_MANIFEST": "/approved/manifests/qwen3-embedding-0.6b.json",
        "EIL_VLLM_EMBEDDING_REVISION": "REPLACE_WITH_REVIEWED_EMBEDDING_MANIFEST_SHA256",
        "EIL_VLLM_EMBEDDING_INPUT_FORMAT": "qwen3",
        "EIL_VLLM_EMBEDDING_DTYPE": "bfloat16",
        "EIL_VLLM_EMBEDDING_TENSOR_PARALLEL_SIZE": "1",
        "EIL_VLLM_EMBEDDING_GPU_MEMORY_UTILIZATION": "0.12",
        "EIL_VLLM_EMBEDDING_MAX_MODEL_LEN": "8192",
        "EIL_VLLM_EMBEDDING_MAX_NUM_SEQS": "2",
    }


def validate_allocation():
    def devices(key):
        raw = os.environ.get(key, "")
        values = raw.split(",")
        if (
            not raw
            or len(values) != len(set(values))
            or any(not re.fullmatch(r"(?:[0-9]+|GPU-[A-Za-z0-9-]+)", v) for v in values)
        ):
            raise ValueError(
                "Use explicit whole-GPU identifiers assigned by Slurm; MIG is not a full-GPU profile"
            )
        return set(values)

    allocated = devices("CUDA_VISIBLE_DEVICES")
    for kind in ("CHAT", "EMBEDDING"):
        selected = devices("EIL_VLLM_" + kind + "_CUDA_VISIBLE_DEVICES")
        key = "EIL_VLLM_" + ("EMBEDDING_" if kind == "EMBEDDING" else "") + "TENSOR_PARALLEL_SIZE"
        size = os.environ.get(key, "1")
        if (
            not re.fullmatch(r"[1-9][0-9]?", size)
            or len(selected) != int(size)
            or not selected <= allocated
        ):
            raise ValueError(
                "Selected GPU count must match tensor parallelism and stay within the Slurm allocation"
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=PROFILES, nargs="?")
    parser.add_argument("--backend", choices=("vllm", "ollama"), default="vllm")
    parser.add_argument("--format", choices=("json", "env"), default="json")
    parser.add_argument("--check-allocation", action="store_true")
    args = parser.parse_args(argv)
    if args.check_allocation:
        try:
            validate_allocation()
        except ValueError as exc:
            parser.error(str(exc))
        print("Slurm GPU selection checked; no device or service was accessed.")
        return 0
    if not args.profile:
        print(json.dumps(PROFILES, indent=2))
        return 0
    env = configuration(args.profile, args.backend)
    if args.format == "env":
        print("# Operator-reviewed template only: replace /approved paths and manifest SHA256s.")
        print("# Supply API keys separately. Vision is opt-in after hardware/model acceptance.")
        for key, value in env.items():
            print(key + "=" + shlex.quote(value))
    else:
        print(
            json.dumps(
                {
                    "profile": args.profile,
                    "backend": args.backend,
                    "plan_only": True,
                    "hardware_validated": False,
                    "upstream_chat": PROFILES[args.profile]["model"]
                    if args.backend == "vllm"
                    else PROFILES[args.profile]["ollama"],
                    "upstream_embedding": "Qwen/Qwen3-Embedding-0.6B"
                    if args.backend == "vllm"
                    else "embeddinggemma:300m",
                    "settings": env,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
