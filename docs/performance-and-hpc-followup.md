# Performance, usability and HPC follow-up

Implementation completed on 2 November 2026, with local model measurements from
1 November. This follows the [project review](project-review-2026-11-01.md).
The user authorized the unfinished refinements, Linux support, a native vLLM
backbone and publication to GitHub, then specified Slurm/NVIDIA and the available
Ollama module. No HPC job, equipment connection or hosted-model run was made.

## What changed

| Area | Result |
| --- | --- |
| Measurement | Content-free stage timings, provider load/prefill/decode counters, derived token rates and first visible output timing in local traces. Missing provider measurements remain unknown. |
| Retrieval | Bounded indexes keyed by authorized source snapshot, scope and embedding identity; archive/reindex invalidation, thread leases and immutable reuse. Persistent derived indexes are opt-in. |
| Chat UX | Optional live stage progress with bounded replay/reconnect, session revocation and cancellation; completed answers keep their final citations. German/English labels remain frozen per run. |
| Administration | Counts for completed, active and attention-needed ingestion jobs, assigned family/machine and indexed passage availability. |
| Sources | Plain-text/Markdown source reads now intersect the requested lines with the actual chunk; legacy snapshots are reconstructed without rewriting their bytes or citation IDs. |
| Answer checks | Recognize exact observed Markdown citation links; check cited passages for selected literal MCU/memory specifications; bounded repairs for unsupported vendor assertions. Explicit uncertainty is preserved. General claim entailment is still unverified. |
| Linux | Bash workbench launcher, LF shell files and Windows/Linux acceptance jobs. |
| HPC | Site-module Ollama Slurm template, optional separately provisioned native vLLM server templates and a bounded local client for generation, classification, embeddings and reviewed vision. |

The existing Ollama/single-agent default, cumulative budgets, owner isolation,
public Siemens query boundary and isolated PDF conversion remain in force.
The [Linux/HPC guide](linux-hpc.md) includes the exact module supplied by the user,
configuration, SSH tunnels, native environment provisioning and unrun GPU checks.

## Measured local performance

Host: NVIDIA GTX 1080 Ti, 11,264 MiB, driver 582.78, Ollama 0.40.6. Tests used
fixed generated prompts or the pinned public Voron pack in isolated report state.
These measurements do not predict a Slurm GPU's throughput.

| Experiment | Observed result | Decision |
| --- | --- | --- |
| Four bounded generations per quantization | Median provider decode: Qwen 3.5 4B Q8_0 **42.77 tokens/s**, Q4_K_M **49.81 tokens/s**. All eight simple generated fact/format checks passed. | Q4 was about 16.5% faster in this small sample; keep Q8 as the app default pending broader quality evidence. |
| Warm output latency | Approximately 62–67 ms to first visible output on the tiny probe; cold calls took seconds. | Record warm/cold policy and loading separately from decode. This is not whole-investigation latency. |
| Embeddings without intervening generation | A 30-second keep-alive reduced the second request to about 25 ms, compared with about 1.85 s under immediate unloading. | Measure contention before changing defaults. |
| Embedding/generation contention at actual 8,192-token context | Only one model was resident at a time. Keeping embeddings for 30 seconds did not survive the generation load; measured generation was about 4.35 s versus 3.64 s under immediate unloading. | Keep the existing unload default. No demonstrated benefit across generation calls. |
| In-process memory index, 857 generated passages | Median cold/warm search **55.35/43.09 ms**, with identical results. | Reuse bounded indexes within a process. Per-run worker processes do not share this memory cache. |
| Persistent index, 63 / 857 / 3,428 passages | Uncached/warm medians **20.83/24.61**, **57.16/52.73**, **166.17/183.44 ms**. | No consistent end-to-end gain. |
| Persistent index, 5,142 passages × 768 dimensions | Uncached/cold/warm medians **403.24/658.49/511.46 ms**, identical results. | Leave `EIL_RETRIEVAL_DISK_CACHE=0` by default; `1` is an operator experiment. |

Provider metrics follow Ollama's [API timing fields](https://docs.ollama.com/api/generate).
Nested retrieval stages overlap and must not be summed. Tool-only/reasoning chunks
do not count as first visible answer output. Native vLLM responses currently have
no measured first-output/decode rate in this adapter; those fields stay unknown.
The live progress stream transmits fixed stage enums, never provisional engineering
claims, hidden reasoning or source content.

Model digests used for the local comparison:

```text
qwen3.5:4b-q8_0    e15635ee93129fd2086640926e900c37589c5167561104abc3914bd6644c7e07
qwen3.5:4b-q4_K_M  d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04
embeddinggemma    b44b2e244cc37dabe08d767b6405d17dbbbdd026bff3797ae37a0f245786d400
```

## Quality results, including failures

Fresh current-code M5 runs passed the unchanged strict base gate: **6/6 for Q8
and 6/6 for Q4**, each covering three cases in single and delegated modes. Q8
median single/delegated wall times were 22.06/30.66 s; Q4 was 20.64/28.66 s.
One repetition per cell is not a statistical ranking. These results include
earlier framework fixes; they cannot be attributed solely to this follow-up.
Original [M5 failures](m5-results.md) and raw baseline artifacts are unchanged.

The separate `eil-voron-quality-followup-v3` uses the public pack, normal chat,
five-call/120-second/32,768-token limits and revised narrow scoring. **4/6 checks
passed**:

| Question | Q8_0 | Q4_K_M |
| --- | --- | --- |
| Controller MCU and bootloader size | Failed: output limit reached before a final answer. | Failed: expected facts appeared, but the citation contract flagged the supporting passage. |
| Documented gantry symptoms | Passed narrow checks. | Passed narrow checks. |
| Unknown error identifier | Passed bounded refusal checks. | Passed bounded refusal checks. |

Earlier v1/v2 outputs remain separate. V1's initial lexical 6/6 score was
insufficient: manual review found an incorrect Q4 controller citation and a
German component mistranslation. That prompted explicit source-range and citation
failure tests and the stricter versioned scorer. V2 also contained output-limit
and citation failures; none was rewritten as a pass. V3's four passes are bounded
fact/format checks, not a guarantee of diagnostic correctness. Claim entailment
is labelled `not_verified`; human review remains necessary. Hosted comparison
is still deferred, and no additional random retries were used to select wins.
Manual review of V3 also found incorrect German paraphrases in both gantry
answers: belts were described as pulleys, and “racked” was mistranslated. The
original English symptoms were present, so the narrow lexical checks passed;
German technical fidelity is **not accepted** by those four passes. The Q8 answer
also opened with an unhelpful denial before listing the documented symptoms.

## Security and compatibility

The vLLM client uses the existing LangChain tool/usage implementation, an explicit
loopback `/v1` endpoint, exact served alias and operator-attested snapshot revision.
It disables redirects, proxy inheritance and retries; bounds request/response bytes;
admits actual local tokenized context before generation; and freezes provider/model
configuration for retries. API keys stay in runtime environment variables, outside
run records. Changing embeddings requires reindexing.

The native vLLM wrapper verifies all regular local snapshot files, including hidden
tokenizer assets, rejects symlinks/external filename references, starts offline and
does not allow custom remote code. The server environment is separate from EIL;
no Torch/vLLM dependency is added to the app. This pin targets vLLM 0.32.0 on a
compatible Linux/NVIDIA GPU, not the local compute-6.1 card.

The provided Ollama 0.14.0 module is a legacy compatibility route with known
advisories. Loopback and reviewed local models reduce exposure but do not patch
it. The [guide](linux-hpc.md#ollama-through-the-site-module) records the affected
issues and recommends an updated site build before private/production use. The
wrapper preserves Slurm GPU visibility and does not invoke an agent shell,
download models, submit jobs or expose a public inference port.

The repeated Bandit scan reports **0 high, 8 medium and 19 low** findings. The
medium findings retain the reviewed fixed/allowlisted SQL and container temporary
path patterns from the previous review. The sole new low finding is B105 on the
literal `return_token_strs=False` tokenizer flag, not a hardcoded credential.
No dependency versions were changed by the optional client extra. Automated
advisory checks remain part of CI; scanner success is not proof of absence of
compromised packages or safe model binaries.

## Validation and reproduction

The final integrated local checks passed:

- Backend: **389 passed, 7 skipped** on Windows. Skips cover Linux-only launcher
  checks and host-dependent capabilities; they are not counted as passes.
- Linux: **17 passed** for the manifest and launcher suite under Ubuntu WSL,
  using generated files and a fake Ollama executable. Bash syntax passed for all
  five shell/Slurm files. No inference service or job was started.
- Frontend: **74 tests across 16 files passed**, with TypeScript/Vite build success.
- Offline base and extended gates: **28/28** scripted single/delegated runs passed.
- Ruff lint/format: **109 files passed**. `uv lock --check` and staged whitespace
  checks passed. Offline supply-chain policy: **189 npm entries, 0 findings**.
- Publication guard: **601 tracked files and current published history, 0 findings**.
- UI verification used only a public/generated fixture: progress opt-in,
  reconnect/cancellation and DE/EN labels, plus the Voron ingestion summary
  (63/63 passages, assigned product family, available). A 390-pixel DOM check
  found no horizontal overflow; it is not a claim of exhaustive mobile validation.

GitHub runs the full offline Windows/Linux and live dependency-advisory jobs on
publication; their status is available from the repository's Actions page.
Generated test states, raw live outputs, model files,
credentials and machine-specific logs remain ignored rather than published.

```bash
uv sync --locked --extra dev --extra hosted --extra inference
uv run ruff check backend/src/eil tests scripts/model_manifest.py
uv run ruff format --check backend/src/eil tests scripts/model_manifest.py
uv run pytest -q
uv run python -m eil.publication --history
uv run python -m eil.supply_chain
uv run python -m eil.benchmark --provider offline --agent-mode both --repetitions 2 --output reports/followup-offline
uv run python -m eil.benchmark_extended --provider offline --agent-mode both --repetitions 2 --output reports/followup-extended
cd frontend
npm ci --ignore-scripts
npm test
npm run build
```

`python -m eil.performance_probe` and `python -m eil.quality_followup` are
plan-only unless explicitly given `--live`. The probe's `--contention` mode adds
the bounded embedding/generation experiment. Use a fresh ignored report directory
and the documented local models; do not substitute private user prompts or paid
providers. Running live tests intentionally consumes local inference resources.

No live vLLM engine, site Ollama module, Slurm allocation, multi-node deployment
or production hardening was validated. PDF ingestion still requires its isolated
converter; use approved text/code exports when the HPC disallows containers.
