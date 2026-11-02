#!/usr/bin/env bash
# Operator-only server wrapper. Models are provisioned separately, never by an agent.
set -euo pipefail
umask 077
check_only=0
case "${1:-}" in
  --help|-h)
    printf '%s\n' 'Usage: bash scripts/start-ollama-hpc.sh [--check]' \
      'Load the site Ollama module first. Requires a private absolute OLLAMA_MODELS directory.'
    exit 0 ;;
  --check) check_only=1 ;;
  '') ;;
  *) printf '%s\n' 'Unknown launcher option; use --help.' >&2; exit 2 ;;
esac
if (( $# > 1 )); then printf '%s\n' 'Too many launcher options.' >&2; exit 2; fi
[[ $(uname -s) == Linux ]] || { printf '%s\n' 'This HPC wrapper requires Linux.' >&2; exit 2; }
command -v ollama >/dev/null || { printf '%s\n' 'Load the site Ollama module before launching.' >&2; exit 2; }
: "${OLLAMA_MODELS:?Set the existing private absolute directory containing reviewed local models}"
[[ "$OLLAMA_MODELS" == /* && -d "$OLLAMA_MODELS" && ! -L "$OLLAMA_MODELS" ]] || {
  printf '%s\n' 'Use an existing absolute model directory, not a symlink.' >&2; exit 2;
}
[[ $(stat -c %u -- "$OLLAMA_MODELS") == "$(id -u)" && $(stat -c %a -- "$OLLAMA_MODELS") == 700 ]] || {
  printf '%s\n' 'The model directory must be owned by this user with mode 0700.' >&2; exit 2;
}
port=${EIL_OLLAMA_PORT:-11435}
[[ "$port" =~ ^[0-9]{4,5}$ ]] && (( 10#$port >= 1024 && 10#$port <= 65535 )) || {
  printf '%s\n' 'Use an unprivileged TCP port.' >&2; exit 2;
}
export OLLAMA_HOST="127.0.0.1:$port"
export OLLAMA_ORIGINS="http://127.0.0.1:$port"
export OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_MAX_QUEUE=8
export OLLAMA_DEBUG=0 OLLAMA_NO_CLOUD=1 OLLAMA_NOPRUNE=1
# Older site builds can ignore OLLAMA_NO_CLOUD; EIL independently rejects cloud aliases.
# Ollama's own logs may contain model paths/metadata: use a private Slurm output file.
printf '%s\n' 'Ollama 0.14.0 has known security advisories; see docs/linux-hpc.md. Use an updated site build for private/production work.' >&2
if (( check_only )); then
  printf '%s\n' 'HPC Ollama configuration verified; no service started, no model downloaded.'
  exit 0
fi
exec ollama serve
