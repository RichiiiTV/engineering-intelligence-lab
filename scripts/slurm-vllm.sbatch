#!/usr/bin/env bash
#SBATCH --job-name=eil-vllm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=01:00:00
# GPU/CPU/memory/account/partition requests are supplied explicitly to sbatch.
# No job is submitted by this repository or by an agent.
set -euo pipefail
umask 077
: "${SLURM_JOB_ID:?Submit this template with sbatch, not on a login node}"
: "${EIL_REPO_DIR:?Set the existing checkout directory before sbatch}"
: "${EIL_VLLM_CHAT_CUDA_VISIBLE_DEVICES:?Choose chat GPU identifiers inside this allocation}"
: "${EIL_VLLM_EMBEDDING_CUDA_VISIBLE_DEVICES:?Choose embedding GPU identifiers inside this allocation}"
cd -- "$EIL_REPO_DIR"
"${EIL_VLLM_PYTHON:?Set the native server Python}" scripts/hpc_profiles.py --check-allocation
children=()
cleanup() {
  local child
  for child in "${children[@]}"; do kill -TERM "$child" 2>/dev/null || true; done
  for child in "${children[@]}"; do wait "$child" 2>/dev/null || true; done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Slurm cgroups/site policy must confine both explicit GPU lists to this allocation.
# Each vLLM server sees only its configured subset; tensor parallelism stays local.
CUDA_VISIBLE_DEVICES="$EIL_VLLM_CHAT_CUDA_VISIBLE_DEVICES" \
  bash scripts/start-vllm-native.sh chat &
children+=("$!")
CUDA_VISIBLE_DEVICES="$EIL_VLLM_EMBEDDING_CUDA_VISIBLE_DEVICES" \
  bash scripts/start-vllm-native.sh embedding &
children+=("$!")
printf '%s\n' 'Native vLLM processes started on compute-node loopback; application connects by local ports or an SSH tunnel.'
# A failed/exited server terminates the paired allocation processes; never auto-retry.
set +e
wait -n "${children[@]}"
result=$?
set -e
exit "$result"
