# GPU model profiles

These operator profiles target the requested whole-GPU Slurm allocations. They
generate configuration only: no model is downloaded, job submitted or provider
changed until the operator explicitly configures and starts it. They are capacity
starting points, **not measured quality/throughput or successful GPU-load results**.

## Native vLLM candidates

| Profile | Allocation | Chat model | Precision / tensor parallel | Chat GPU fraction / sequences |
| --- | --- | --- | --- | --- |
| `l40s` | 1 × L40S, 48 GB | Qwen/Qwen3.5-9B | BF16 / 1 | 0.75 / 2 |
| `a100-40gb` | 1 × A100, 40 GB | Qwen/Qwen3.5-9B | BF16 / 1 | 0.75 / 2 |
| `a100-80gb` | 1 × A100, 80 GB | Qwen/Qwen3.5-27B | BF16 / 1 | 0.80 / 1 |
| `a100-40gb-x4` | 4 × A100, 40 GB, one node | Qwen/Qwen3.5-35B-A3B | BF16 / 4 | 0.78 / 2 |

All use **Qwen/Qwen3-Embedding-0.6B**, BF16, TP=1, fraction 0.12 and at most two
scheduled sequences on one of the allocated chat GPUs. Chat and embedding context
are capped at 8,192 tokens; chat output stays within the existing 2,048-token
server ceiling and each run's smaller output/total budgets. The embedding model
produces 1,024-dimensional vectors, within EIL's current bound.

BF16 avoids assuming native FP8 support on A100. The language-model weights alone
are roughly 18/54/70 GB for the 9B/27B/35B choices at two bytes per parameter;
actual allocations also include vision weights, recurrent/KV state, activations,
CUDA graphs and runtime workspaces. All MoE weights must fit despite only a
subset being active per token. TP does not guarantee a speedup: PCIe/NVLink topology
and architecture matter. The dense 27B candidate may be preferable for quality;
no ranking is established here. Four 40 GB devices are not one contiguous 160 GB
allocation. Use exclusive/site-isolated full GPUs, not MIG slices or shared nodes
with untrusted co-tenants.

Upstream references checked on 2 November 2026:

- [Qwen 3.5 9B](https://huggingface.co/Qwen/Qwen3.5-9B),
  [27B](https://huggingface.co/Qwen/Qwen3.5-27B) and
  [35B-A3B configuration](https://huggingface.co/Qwen/Qwen3.5-35B-A3B/blob/main/config.json).
- [Qwen3 Embedding 0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B):
  multilingual retrieval and query instructions; documents need no such instruction.
- [vLLM 0.32 architectures](https://docs.vllm.ai/en/v0.32.0/models/supported_models/)
  and [hardware/quantization matrix](https://docs.vllm.ai/en/v0.32.0/features/quantization/).
- The pinned [tool parser registry](https://github.com/vllm-project/vllm/blob/v0.32.0/vllm/tool_parsers/__init__.py)
  maps `qwen3_coder` and `qwen3_xml` to the same built-in parser.

The native profiles use the existing **vLLM 0.32.0** pin. Some model cards still
contain older nightly-install instructions; do not replace the reviewed pin with
an unreviewed nightly. Match its CUDA/PyTorch wheel requirements to the actual
driver, not just the CUDA version in the unrelated Ollama module name. No custom
remote code, automatic quantization, CPU offload or expert-parallel network
service is enabled. Review licenses and materialize pinned local snapshots using
the [HPC guide](linux-hpc.md); mutable model IDs alone are not snapshot revisions.

## Generate and configure

```bash
python scripts/hpc_profiles.py                         # list choices; no side effects
python scripts/hpc_profiles.py a100-80gb                # JSON plan
umask 077
install -d -m 700 .eil
python scripts/hpc_profiles.py a100-80gb --format env > .eil/hpc.env
```

Review the generated file. Replace `/approved/...` paths and both manifest hashes
with your reviewed local values. The aliases are served names; upstream model
references identify the weights to provision separately. Keep private snapshot
names and generated configuration outside Git. The template contains no API key
and intentionally cannot start with placeholder revisions. Use the site's approved
provisioning process; do not download weights on a login node.

Load the trusted, reviewed file in the operator shell and provide the environment,
private cache and runtime API key described in the HPC guide:

```bash
set -a
source .eil/hpc.env
set +a
export EIL_REPO_DIR="$PWD"
export EIL_VLLM_PYTHON=/approved/envs/eil-vllm/bin/python
export EIL_VLLM_CACHE_DIR=/approved/private-vllm-cache
# Supply EIL_VLLM_API_KEY through the site's private secret mechanism.
bash scripts/start-vllm-native.sh chat --check
bash scripts/start-vllm-native.sh embedding --check
```

Submit `scripts/slurm-vllm.sbatch` using site-specific account/partition, GPU count,
CPU/memory and private output-log settings. Inside that job, after Slurm assigns
its GPU environment and before the template's validation/launch section, set:

```bash
export EIL_VLLM_CHAT_CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES"
export EIL_VLLM_EMBEDDING_CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES##*,}"
python scripts/hpc_profiles.py --check-allocation
```

Alternatively supply those lists through a site wrapper that preserves the
allocation. Never guess host GPU numbers in the login shell. The template checks
that selected lists contain no duplicates, are subsets of Slurm's assigned list
and match each server's TP count. It stops before model loading on mismatch.
This is a visibility check, not proof of GPU type, free VRAM or usable drivers.
Startup may still fail; inspect private logs and lower concurrency/use a smaller
reviewed model rather than silently changing precision.

Copy matching provider/model/revision/input-format settings to EIL's private app
environment. The app does not source shell files. Keep SSH endpoints on loopback.
Changing embedding provider, model, revision **or input format** requires reindexing.
The `qwen3` input format converts EIL's query wrapper to the upstream
`Instruct: ...\nQuery: ...` convention while leaving document inputs intact. Its
identity suffix prevents mixing with an old vector index. This choice is frozen
on queued ingestion and investigation runs, including retries.

Vision stays explicitly **off** in templates. After testing the checkpoint with
a generated normalized JPEG, set `EIL_VLLM_VISION=1` in both app and server to
allow one image and no video/audio per request. Its processor cache is disabled.
Text-only mode disables multimodal inputs, reducing startup/profile memory.
Images never become external URLs.

## Legacy Ollama module alternative

`python scripts/hpc_profiles.py PROFILE --backend ollama --format env` generates
the separate module-compatible configuration. It selects `qwen3:14b-q8_0` for
L40S / A100 40 GB and `qwen3:32b-q8_0` for A100 80 GB / four A100 40 GB, with the
existing EmbeddingGemma 300M. These are older **text-only** tool-capable candidates,
not Qwen 3.5 vision models. The [14B](https://ollama.com/library/qwen3:14b-q8_0)
and [32B](https://ollama.com/library/qwen3:32b-q8_0) registry entries report about
16 GB and 35 GB. The four-GPU route requests spread scheduling, not vLLM tensor
parallelism; no latency benefit or efficient VRAM utilization is established.

The supplied `ollama/0.14.0-GCCcore-13.3.0-CUDA-12.6.3` module still needs its
security update/review and site-build validation. A larger model does not patch
that server. No profile accepts model terms, downloads weights, changes Slurm's
assigned visibility or patches the module. The default local app stays unchanged.

## Acceptance on the actual allocation

Record exact GPU model/count, driver, server version, model manifests and free
VRAM. Verify both aliases and vector dimensions, index a generated document, then
test DE/EN chat/tools, controller citations, wrong-source rejection, unknown alarm
refusal, cancellation/resume and optional generated-image input. The same bounded
public fixture can target the configured native or Ollama profile:

```bash
uv run --locked --extra inference python -m eil.quality_followup --configured
uv run --locked --extra inference python -m eil.quality_followup --configured --live --output reports/hpc-profile-quality-v1
```

The first command is plan-only. The second uses the chosen local provider and
three fixed public questions, not private user prompts. Outputs distinguish an
ordinary model answer from a clearly labelled source-excerpt fallback and retain
the failed draft contract. A fallback is not a model-quality pass. Measure
warm/cold latency, token rate and peak memory with both servers resident. All
four profiles remain **hardware-unvalidated** until these checks run on the HPC.
