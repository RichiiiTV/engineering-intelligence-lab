#!/usr/bin/env bash
#SBATCH --job-name=eil-ollama
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=01:00:00
# Supply site account/partition/GPU/CPU/memory and private --output to sbatch.
set -euo pipefail
umask 077
: "${SLURM_JOB_ID:?Submit this template with sbatch, not on a login node}"
: "${EIL_REPO_DIR:?Set the existing checkout directory before sbatch}"
if ! type module >/dev/null 2>&1; then
  printf '%s\n' 'Initialize the site module system in this job shell using site instructions.' >&2
  exit 2
fi
module load "${EIL_HPC_OLLAMA_MODULE:-ollama/0.14.0-GCCcore-13.3.0-CUDA-12.6.3}"
cd -- "$EIL_REPO_DIR"
# Preserve the CUDA_VISIBLE_DEVICES assigned by Slurm. Never select host GPUs here.
# Foreground exec lets Slurm signal/account for the server directly; no background daemon.
exec bash scripts/start-ollama-hpc.sh
