# Linux and Slurm/NVIDIA inference

EIL runs on Linux as well as Windows. Ollama remains the default backend. The
optional `inference` extra adds the client for a self-hosted, OpenAI-compatible
vLLM server; it does not install vLLM, start a paid provider or download weights.
Generation, embeddings and classification use the explicitly selected backend.

The server scripts target **Slurm with NVIDIA GPUs**, as requested. Use the site's
Ollama module first; vLLM is an optional separate environment and needs no module.
Neither route uses Docker for inference. The
operator must choose the account, partition, GPU allocation, model snapshots,
tool-call parser and memory limits. No cluster job has been submitted or tested
on the user's HPC. Linux CI and local Bash/protocol checks are separate from a
real GPU deployment test.

## Start the app on Linux

Use Python 3.12+, `uv`, Node.js 22.12+ or 24, and npm. Use a separate Linux
checkout/environment rather than sharing Windows `.venv` or `node_modules`
binaries with WSL/Linux. From that checkout:

```bash
umask 077
uv sync --locked --extra dev --extra inference
cp .env.example .env
bash scripts/start-workbench.sh
```

The launcher installs locked frontend packages with dependency hooks disabled,
builds the UI, and serves **http://127.0.0.1:8000/**. For a prebuilt UI, pass
`--skip-build`. In another terminal run
`uv run --locked --extra inference python -m eil.cli auth-bootstrap` to create
the first administrator with a one-time setup code. No default password exists.
The launcher does not start a model server. With the default configuration, start
Ollama locally and install the models described in [Getting started](getting-started.md).

Use one API service per state directory. On a shared cluster, place
`EIL_STATE_DIR` in an operator-owned, mode-0700 directory on an approved local
filesystem; keep model manifests, API keys, logs and backups private too. The
scripts use `umask 077`. Loopback binding and application authentication do not
replace filesystem permissions or cluster access controls.

Plain text, Markdown, code exports and problem images/logs do not require Docker.
**PDF conversion retains the isolated container boundary.** Native inference does
not enable unsandboxed in-process PDF parsing. If the cluster forbids containers,
provide approved text/code exports or convert public material using an approved
isolated ingestion host. See [PDF operations](security-operations.md#isolated-pdf-conversion).

## Prepare a separate native server environment

For the module-based route, use the [Ollama instructions below](#ollama-through-the-site-module).
The following sections describe the optional vLLM alternative.

The reviewed server pin is **vLLM 0.32.0**, the official stable release checked on
1 November 2026. It runs on Linux, and the current NVIDIA requirement is compute
capability **7.5 or newer**. The local GTX 1080 Ti is compute 6.1 and was not used
to claim vLLM hardware validation. Match the cluster's driver/CUDA/PyTorch stack
to the official installation instructions. Keep this environment separate from
EIL's client environment. [Release](https://github.com/vllm-project/vllm/releases/tag/v0.32.0),
[GPU installation](https://docs.vllm.ai/en/v0.32.0/getting_started/installation/gpu/).

On a provisioning host permitted by the cluster operator:

```bash
uv venv --python 3.12 /approved/envs/eil-vllm
uv pip install --python /approved/envs/eil-vllm/bin/python 'vllm==0.32.0'
```

This provisioning step needs package access unless the site supplies an approved
wheelhouse. The launch scripts install nothing. Prepare **materialized local
model directories** with reviewed weights, config, tokenizer and chat template
files. Pin the upstream snapshot and review its license; do not use mutable model
IDs as a substitute for a snapshot. The servers start offline and never enable
`trust_remote_code`. Architectures requiring custom model code are unsupported
by these scripts.

Chat needs a model whose template/tool parser supports vLLM auto tool calling and
structured outputs. Embeddings need a compatible pooling model with the desired
vector dimensions. Select these using the upstream model documentation and
[vLLM serving arguments](https://docs.vllm.ai/en/v0.32.0/cli/serve/); a server's
successful startup alone does not establish diagnostic quality.

## Review and verify model snapshots

Create a manifest for each local directory, outside that directory:

```bash
install -d -m 700 .eil/model-manifests
python scripts/model_manifest.py /approved/models/chat \
  --output .eil/model-manifests/chat-v1.json
python scripts/model_manifest.py /approved/models/embedding \
  --output .eil/model-manifests/embedding-v1.json
```

Each command prints a SHA-256 revision for the exact manifest bytes. Save those
revisions in the private runtime configuration. The helper streams file hashes,
stores relative names only and refuses symlinks, missing tokenizer/weights,
overwrites and changed snapshots. An HF cache containing symlinked assets must
first be materialized into a reviewed directory. Revisions are not secrets;
private model names/manifests may nevertheless be organization-sensitive and
must stay outside Git.

The native wrappers verify every listed local file and the manifest revision
before starting. The EIL client separately checks the exact served model alias
at its configured loopback `/v1/models` endpoint before sending text. The client
revision is an operator attestation, not cryptographic remote attestation of an
HPC server's internals. Reindex documents after changing embedding provider,
model or revision; old vector identities must not be reused under a new model.

## Native server configuration

Set these in the operator environment or a private, trusted environment file.
The shell scripts do **not** source the app's `.env` file. Do not put API keys in
`sbatch` command lines, model manifests, repository files or shared logs.

```bash
export EIL_VLLM_PYTHON=/approved/envs/eil-vllm/bin/python
install -d -m 700 /approved/private-vllm-cache
export EIL_VLLM_CACHE_DIR=/approved/private-vllm-cache
export EIL_VLLM_MODEL_PATH=/approved/models/chat
export EIL_VLLM_MANIFEST="$PWD/.eil/model-manifests/chat-v1.json"
export EIL_VLLM_MODEL=eil-chat
export EIL_VLLM_REVISION=REPLACE_WITH_PRINTED_CHAT_MANIFEST_SHA256
export EIL_VLLM_TOOL_CALL_PARSER=REPLACE_WITH_MODEL_COMPATIBLE_BUILTIN_PARSER

export EIL_VLLM_EMBEDDING_MODEL_PATH=/approved/models/embedding
export EIL_VLLM_EMBEDDING_MANIFEST="$PWD/.eil/model-manifests/embedding-v1.json"
export EIL_VLLM_EMBEDDING_MODEL=eil-embed
export EIL_VLLM_EMBEDDING_REVISION=REPLACE_WITH_PRINTED_EMBEDDING_MANIFEST_SHA256

# Supply a unique private EIL_VLLM_API_KEY through the site's approved secret mechanism.
# EIL_VLLM_EMBEDDING_API_KEY may be distinct; otherwise it uses that same key.
bash scripts/start-vllm-native.sh chat --check
bash scripts/start-vllm-native.sh embedding --check
```

`--check` verifies configuration and local bytes without importing vLLM, opening a
port or contacting a model. To run on an allocated Linux GPU node, launch the
same commands without `--check` in separate terminals/processes. Servers bind
only **127.0.0.1:8002** and **127.0.0.1:8003**. API keys are passed through
`VLLM_API_KEY`, never process arguments. Request/output/access logs and usage
telemetry are disabled. Authentication does not protect every vLLM endpoint;
keep the loopback boundary. [Server security](https://docs.vllm.ai/en/v0.32.0/usage/security/).

Loopback is host-wide on a shared compute node. Use a private allocation or
site-approved isolation/access controls; an API key alone is insufficient to
isolate this service from untrusted co-tenants. Keep model/compiler caches in a
private operator-owned location as required by the cluster policy.
The wrapper checks ownership/mode of the configured cache root and places vLLM,
Triton and Inductor caches beneath it. Remote media domains are restricted to an
unresolvable reserved domain, redirects are disabled and local media paths remain
disabled. EIL supplies supported images as bounded inline data rather than URLs.
Prefix caching is disabled to avoid implicitly sharing cached private prompt
prefixes between workspace accounts. This trades a possible performance gain for
the existing privacy boundary; per-owner cache salting is not implemented here.

Chat defaults to 8,192 context tokens; embeddings default to 2,048. Override with
`EIL_VLLM_MAX_MODEL_LEN` and `EIL_VLLM_EMBEDDING_MAX_MODEL_LEN`, respectively
(integers 1–8,192). Each value must also fit the model's declared maximum: for a
512-token pooling model, set `EIL_VLLM_EMBEDDING_MAX_MODEL_LEN=512`. The wrapper
never enables vLLM's unsafe long-context override. Oversized embedding inputs
fail rather than silently truncating; choose a model suitable for EIL's passage
sizes and validate indexing on the real allocation.
Both servers default to at most eight scheduled sequences,
tensor parallel size 1, and GPU memory utilization 0.8 **per server**. Give them
separate allocated GPUs, or explicitly lower both memory fractions if sharing a
GPU. Choose limits appropriate to model size and available VRAM. Configure with
`EIL_VLLM_TENSOR_PARALLEL_SIZE` / `EIL_VLLM_GPU_MEMORY_UTILIZATION` and corresponding
`EIL_VLLM_EMBEDDING_*` variables. No hardware-specific throughput is promised.
The chat server also caps generated responses at 2,048 tokens; application
per-call/cumulative budgets still apply.

## Slurm allocation

The template requests one node/task and a one-hour limit. It leaves resource
requests to the operator. Do not run inference on a login node. For example,
after replacing the site-specific placeholders and selecting GPU identifiers
inside the allocation:

```bash
export EIL_REPO_DIR="$PWD"
export EIL_VLLM_CHAT_CUDA_VISIBLE_DEVICES=REPLACE_WITH_ALLOCATED_CHAT_GPU_LIST
export EIL_VLLM_EMBEDDING_CUDA_VISIBLE_DEVICES=REPLACE_WITH_ALLOCATED_EMBEDDING_GPU_LIST
sbatch --account=SITE_ACCOUNT --partition=SITE_GPU_PARTITION \
  --gres=gpu:REQUESTED_COUNT --cpus-per-task=SITE_CPU_COUNT --mem=SITE_MEMORY \
  --output=/approved/private-logs/eil-vllm-%j.log scripts/slurm-vllm.sbatch
```

Use your site's accepted `--gres` or `--gpus` form; do not request resources that
the selected account/partition does not permit. Both child servers inherit the
allocation. Site cgroups/GPU isolation must confine the explicitly supplied GPU
lists to that allocation. The template terminates its paired servers on an exit
or cancellation and does not retry unknown outcomes. It never submits another
job or starts Docker. Tensor parallelism is single-node; distributed multi-node
vLLM/Ray deployment is outside this template.
Distributed-control addresses and NCCL/Gloo socket interfaces are fixed to
loopback for this single-node design. Do not reuse it as a multi-node network
configuration.

## Connect EIL without exposing a port

Run EIL in the same allocation and use its loopback endpoints, or keep the app on
the workstation and create an authorized SSH tunnel through the site's login
node to the allocated compute node:

```bash
ssh -N -o ExitOnForwardFailure=yes -J LOGIN_HOST \
  -L 127.0.0.1:8002:127.0.0.1:8002 \
  -L 127.0.0.1:8003:127.0.0.1:8003 COMPUTE_HOST
```

The final SSH destination is the compute node, so both remote forwarding targets
are its loopback interface. Use approved SSH configuration/authentication and
verify the host normally. Do not bypass host-key warnings or bind the forwarded
ports to a public interface.

Set the app's private `.env` or process environment:

```dotenv
EIL_MODEL_PROVIDER=vllm
EIL_VLLM_BASE_URL=http://127.0.0.1:8002/v1
EIL_VLLM_MODEL=eil-chat
EIL_VLLM_REVISION=REPLACE_WITH_PRINTED_CHAT_MANIFEST_SHA256
EIL_VLLM_VISION=0
EIL_EMBEDDING_PROVIDER=vllm
EIL_VLLM_EMBEDDING_BASE_URL=http://127.0.0.1:8003/v1
EIL_VLLM_EMBEDDING_MODEL=eil-embed
EIL_VLLM_EMBEDDING_REVISION=REPLACE_WITH_PRINTED_EMBEDDING_MANIFEST_SHA256
```

Provide the matching API keys separately in the app's environment. Ordinary run
configuration freezes the chosen provider/model/revision for retries; changing
server configuration does not reset usage budgets. Hosted OpenAI validation
remains a separate, explicitly configured workflow.

## Acceptance and limits

Linux CI runs the same offline backend/frontend acceptance gates as Windows and
checks Bash launcher syntax/help. Manifest tests cover changed/missing assets,
traversal-like manifest entries, symlinks and overwrite refusal. Adapter tests use
mocked loopback protocol responses and real framework tool binding; they are not
a live vLLM GPU or Slurm acceptance result.

Local Ubuntu WSL checks passed Bash syntax/help and six generated-only native
launcher checks: valid chat/embedding configuration, invalid port/revision/parser
and zero memory fraction. They started no service and submitted no job.
The focused manifest/launcher pytest suite also passed **11 tests under Ubuntu
WSL** using its Linux Python/Bash runtime. This validates local files and shell
control flow, not GPU inference.

On the real allocation, the operator still needs to verify model loading,
tool-call parser compatibility, exact model aliases, embedding reindexing,
private-state permissions, session revocation, interrupted/retried runs and the
public/generated quality suite. Record model manifests, vLLM/driver versions,
GPU type/count and limits before comparing latency. Do not treat an unavailable
cluster or an unrun GPU test as a pass.

## Ollama through the site module

The user reports this available module:

```bash
module load ollama/0.14.0-GCCcore-13.3.0-CUDA-12.6.3
```

EIL already uses Ollama's HTTP API; this route needs no vLLM installation or
`inference` extra. The Python `ollama` client package and the server module have
independent version numbers. The v0.14.0 API includes tools, JSON schema output,
thinking controls, embeddings and model metadata used by the adapter. This is
source-level compatibility, **not a completed test of the site's module build**.
[Pinned API source](https://github.com/ollama/ollama/blob/v0.14.0/api/types.go).

**Version 0.14.0 is a legacy compatibility target, not a security recommendation.**
It falls within the affected range for the GGUF loader issue
[CVE-2026-7482](https://github.com/advisories/GHSA-x8qc-fggm-mpqg) and the separate
experimental agent approval issue
[CVE-2026-102697](https://www.cve.org/CVERecord?id=CVE-2026-102697).
EIL uses `ollama serve`, never Ollama's experimental shell agent or model-creation
API, and accepts only downloaded local GGUF aliases. Those restrictions do not
patch the server. Request an updated, site-supported module before handling
private material or production use. A build number alone cannot establish whether
the HPC administrators have backported fixes.

The launcher fixes the bind address to `127.0.0.1:11435`, one parallel request,
one loaded model and an 8,192-token context. It preserves Slurm's
`CUDA_VISIBLE_DEVICES`. It requires an existing, operator-owned mode-0700 model
directory, installs/downloads nothing and starts only a foreground server.
`OLLAMA_NO_CLOUD=1` is set for builds that support it; older builds may ignore it.
EIL independently rejects remote/cloud aliases before sending private content.
The server API itself has no authentication: use an exclusive/site-isolated node
and an SSH tunnel. Loopback is reachable by other users on the same host.

Prepare the reviewed model store through the site's approved provisioning process
on a node where downloading is permitted. **Do not assume the current Qwen 3.5
default works on 0.14.0.** Explicitly select a locally supported model with tools
and structured-output support; `qwen3:4b` is an older text-only candidate that still
needs live quality validation. Images require a compatible, separately reviewed
vision model. Do not silently change embedding models on an indexed catalog.
[Qwen3 model capabilities](https://ollama.com/library/qwen3:4b).

```bash
module load ollama/0.14.0-GCCcore-13.3.0-CUDA-12.6.3
install -d -m 700 /approved/private-ollama-models /approved/private-logs
export OLLAMA_MODELS=/approved/private-ollama-models
export EIL_REPO_DIR="$PWD"
bash scripts/start-ollama-hpc.sh --check
sbatch --account=SITE_ACCOUNT --partition=SITE_GPU_PARTITION \
  --gres=gpu:1 --cpus-per-task=SITE_CPU_COUNT --mem=SITE_MEMORY \
  --output=/approved/private-logs/eil-ollama-%j.log scripts/slurm-ollama.sbatch
```

The template loads the reported module inside the job. If the batch shell has no
`module` function, initialize it using the site's documented shell setup; the
template stops with an actionable error rather than sourcing an arbitrary script.
Use `EIL_HPC_OLLAMA_MODULE` to select an updated site module. Model files must
already be present; an empty store passes the filesystem check but cannot answer.
`--check` performs configuration checks only, without executing Ollama.

Connect the workstation to the allocated compute node, then configure the app:

```bash
ssh -N -o ExitOnForwardFailure=yes -J LOGIN_HOST \
  -L 127.0.0.1:11435:127.0.0.1:11435 COMPUTE_HOST
```

```dotenv
EIL_MODEL_PROVIDER=ollama
EIL_EMBEDDING_PROVIDER=ollama
EIL_OLLAMA_BASE_URL=http://127.0.0.1:11435
EIL_OLLAMA_MODEL=qwen3:4b
EIL_EMBEDDING_MODEL=embeddinggemma:300m
```

Both model names are explicit examples, not an assertion that they are installed
on the cluster. In an authorized allocation, check `ollama --version`,
`OLLAMA_HOST=127.0.0.1:11435 ollama list` and `ollama ps`, then run a generated-only
chat/tool-call, structured-classification and embedding/indexing smoke test through
EIL. Check citations, refusal behavior, cancellation and limits before admitting
private content. Keep Slurm output private: upstream logs can include paths and
model metadata. Stop the job with the site's normal `scancel JOB_ID` procedure.
No job or connection to the user's HPC was made during this implementation.
