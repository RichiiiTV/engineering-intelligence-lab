#!/usr/bin/env bash
# Operator launcher only. Never exposed as an agent tool.
set -euo pipefail
umask 077
repo_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$repo_dir"
skip_build=0
case "${1:-}" in
  --help|-h)
    printf '%s\n' 'Usage: bash scripts/start-workbench.sh [--skip-build]' \
      'Serves EIL on 127.0.0.1:8000 using the configured Ollama or vLLM backend.'
    exit 0 ;;
  --skip-build) skip_build=1 ;;
  '') ;;
  *) printf '%s\n' 'Unknown launcher option; use --help.' >&2; exit 2 ;;
esac
if (( $# > 1 )); then printf '%s\n' 'Too many launcher options.' >&2; exit 2; fi
command -v uv >/dev/null || { printf '%s\n' 'Install uv before launching EIL.' >&2; exit 2; }
export UV_CACHE_DIR="${UV_CACHE_DIR:-$repo_dir/.uv-cache}"
if (( ! skip_build )); then
  command -v npm >/dev/null || { printf '%s\n' 'Install Node.js/npm before building the UI.' >&2; exit 2; }
  (
    cd frontend
    if [[ ! -d node_modules ]]; then npm ci --ignore-scripts; fi
    npm run build
  )
fi
if [[ ! -f frontend/dist/index.html ]]; then
  printf '%s\n' 'The built UI is missing. Run the launcher without --skip-build first.' >&2
  exit 2
fi
printf '%s\n' 'Workbench: http://127.0.0.1:8000/ (Ctrl+C to stop)'
# The client extra does not install vLLM, PyTorch or a hosted service.
exec uv run --locked --extra inference uvicorn eil.api:app \
  --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5 --no-access-log
