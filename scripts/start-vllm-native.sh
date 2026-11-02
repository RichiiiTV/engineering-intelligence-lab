#!/usr/bin/env bash
# A local, operator-configured native vLLM process. No container or remote-code plugins.
set -euo pipefail
umask 077
repo_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mode=${1:-}
check_only=0
if [[ "$mode" == --help || "$mode" == -h ]]; then
  printf '%s\n' 'Usage: bash scripts/start-vllm-native.sh chat|embedding [--check]' \
    'Reads explicit local model paths/manifests and loopback configuration; see docs/linux-hpc.md.'
  exit 0
fi
if [[ "$mode" != chat && "$mode" != embedding ]]; then
  printf '%s\n' 'Choose chat or embedding; use --help.' >&2; exit 2
fi
if [[ "${2:-}" == --check && $# -eq 2 ]]; then check_only=1
elif (( $# != 1 )); then printf '%s\n' 'Unknown native-server option.' >&2; exit 2
fi
[[ $(uname -s) == Linux ]] || { printf '%s\n' 'Native vLLM requires Linux.' >&2; exit 2; }
: "${EIL_VLLM_PYTHON:?Set EIL_VLLM_PYTHON to the separate vLLM environment python}"
[[ -x "$EIL_VLLM_PYTHON" ]] || { printf '%s\n' 'The configured vLLM Python is not executable.' >&2; exit 2; }
: "${EIL_VLLM_CACHE_DIR:?Set an existing private owner-only cache directory}"
"$EIL_VLLM_PYTHON" - "$EIL_VLLM_CACHE_DIR" <<'PY'
import os,stat,sys
from pathlib import Path
p=Path(sys.argv[1])
if not p.is_absolute() or p.is_symlink() or not p.is_dir():
    raise SystemExit('Use an existing absolute private cache directory, not a symlink')
s=p.stat()
if s.st_uid!=os.geteuid() or stat.S_IMODE(s.st_mode)&0o777!=0o700:
    raise SystemExit('The native cache directory must be owned by this user with mode0700 and no group/other permissions')
PY
if [[ "$mode" == chat ]]; then
  : "${EIL_VLLM_MODEL_PATH:?Set the prefetched local chat model directory}"
  : "${EIL_VLLM_MANIFEST:?Set the reviewed chat model manifest file}"
  : "${EIL_VLLM_MODEL:?Set the explicit served chat alias}"
  : "${EIL_VLLM_REVISION:?Set the reviewed manifest SHA256}"
  : "${EIL_VLLM_API_KEY:?Set a private runtime API key}"
  : "${EIL_VLLM_TOOL_CALL_PARSER:?Set the model-compatible built-in tool parser}"
  model_path=$EIL_VLLM_MODEL_PATH
  manifest=$EIL_VLLM_MANIFEST
  alias=$EIL_VLLM_MODEL
  revision=$EIL_VLLM_REVISION
  port=${EIL_VLLM_PORT:-8002}
  parallel=${EIL_VLLM_TENSOR_PARALLEL_SIZE:-1}
  memory=${EIL_VLLM_GPU_MEMORY_UTILIZATION:-0.8}
  model_len=${EIL_VLLM_MAX_MODEL_LEN:-8192}
  export VLLM_API_KEY=$EIL_VLLM_API_KEY
else
  : "${EIL_VLLM_EMBEDDING_MODEL_PATH:?Set the prefetched local embedding model directory}"
  : "${EIL_VLLM_EMBEDDING_MANIFEST:?Set the reviewed embedding model manifest file}"
  : "${EIL_VLLM_EMBEDDING_MODEL:?Set the explicit served embedding alias}"
  : "${EIL_VLLM_EMBEDDING_REVISION:?Set the reviewed embedding manifest SHA256}"
  model_path=$EIL_VLLM_EMBEDDING_MODEL_PATH
  manifest=$EIL_VLLM_EMBEDDING_MANIFEST
  alias=$EIL_VLLM_EMBEDDING_MODEL
  revision=$EIL_VLLM_EMBEDDING_REVISION
  port=${EIL_VLLM_EMBEDDING_PORT:-8003}
  parallel=${EIL_VLLM_EMBEDDING_TENSOR_PARALLEL_SIZE:-1}
  memory=${EIL_VLLM_EMBEDDING_GPU_MEMORY_UTILIZATION:-0.8}
  model_len=${EIL_VLLM_EMBEDDING_MAX_MODEL_LEN:-2048}
  export VLLM_API_KEY=${EIL_VLLM_EMBEDDING_API_KEY:-${EIL_VLLM_API_KEY:-}}
  [[ -n "$VLLM_API_KEY" ]] || { printf '%s\n' 'Set the embedding runtime API key.' >&2; exit 2; }
fi
[[ "$model_path" == /* && -d "$model_path" ]] || { printf '%s\n' 'Use an existing absolute local model directory.' >&2; exit 2; }
[[ "$revision" =~ ^[0-9a-f]{64}$ ]] || { printf '%s\n' 'Revision must be a lowercase SHA256.' >&2; exit 2; }
[[ "$alias" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$ ]] || { printf '%s\n' 'Invalid served alias.' >&2; exit 2; }
[[ "$port" =~ ^[0-9]{4,5}$ ]] && (( 10#$port >= 1024 && 10#$port <= 65535 )) || { printf '%s\n' 'Use an unprivileged TCP port.' >&2; exit 2; }
[[ "$parallel" =~ ^[1-9][0-9]?$ ]] || { printf '%s\n' 'Invalid tensor parallel size.' >&2; exit 2; }
[[ "$model_len" =~ ^[1-9][0-9]{0,3}$ ]] && (( 10#$model_len <= 8192 )) || { printf '%s\n' 'Model length must be from 1 through 8192 tokens.' >&2; exit 2; }
[[ "$memory" =~ ^0\.[0-9]+$ ]] || { printf '%s\n' 'GPU memory utilization must be between 0 and 1.' >&2; exit 2; }
"$EIL_VLLM_PYTHON" -c 'import sys; sys.exit(0 if 0<float(sys.argv[1])<1 else "GPU memory utilization must be between 0 and 1")' "$memory"
if [[ "$mode" == chat && ! "$EIL_VLLM_TOOL_CALL_PARSER" =~ ^[A-Za-z0-9_-]{1,80}$ ]]; then
  printf '%s\n' 'Use a built-in tool parser name, not a plugin path.' >&2; exit 2
fi
# Exported env values are not printed or placed in process command-line arguments.
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
export VLLM_NO_USAGE_STATS=1 VLLM_DO_NOT_TRACK=1 DO_NOT_TRACK=1
export VLLM_DEBUG_LOG_API_SERVER_RESPONSE=False VLLM_LOGGING_LEVEL=WARNING
export VLLM_TRACE_FUNCTION=0
export VLLM_HOST_IP=127.0.0.1 NCCL_SOCKET_IFNAME=lo GLOO_SOCKET_IFNAME=lo
export VLLM_CACHE_ROOT="$EIL_VLLM_CACHE_DIR/vllm"
export TRITON_CACHE_DIR="$EIL_VLLM_CACHE_DIR/triton"
export TORCHINDUCTOR_CACHE_DIR="$EIL_VLLM_CACHE_DIR/torchinductor"
export VLLM_MEDIA_URL_ALLOW_REDIRECTS=0 VLLM_MAX_MEDIA_DOWNLOAD_SIZE_MB=10 VLLM_MAX_IMAGE_PIXELS=25000000
"$EIL_VLLM_PYTHON" "$repo_dir/scripts/model_manifest.py" "$model_path" \
  --verify "$manifest" --expected-sha256 "$revision"
if (( check_only )); then
  printf '%s\n' 'Native vLLM configuration and local snapshot verified; no service started.'
  exit 0
fi
"$EIL_VLLM_PYTHON" -c 'import importlib.metadata,sys; sys.exit(0 if importlib.metadata.version("vllm")=="0.32.0" else "Install the reviewed vllm==0.32.0 server version")'
args=(serve "$model_path" --tokenizer "$model_path" --served-model-name "$alias"
  --host 127.0.0.1 --port "$port" --tensor-parallel-size "$parallel"
  --gpu-memory-utilization "$memory" --max-model-len "$model_len" --max-num-seqs 8
  --allowed-media-domains eil-no-remote-media.invalid
  --no-trust-remote-code --no-trust-request-chat-template --no-trust-request-mm-kwargs
  --no-enable-prefix-caching
  --no-enable-log-requests --no-enable-log-outputs --no-enable-log-deltas
  --disable-uvicorn-access-log --disable-log-stats --disable-fastapi-docs)
if [[ "$mode" == chat ]]; then
  args+=(--runner generate --enable-auto-tool-choice --tool-call-parser "$EIL_VLLM_TOOL_CALL_PARSER"
    --generation-config vllm --override-generation-config '{"max_new_tokens":2048}')
else
  args+=(--runner pooling)
fi
exec "$EIL_VLLM_PYTHON" -m vllm.entrypoints.cli.main "${args[@]}"
