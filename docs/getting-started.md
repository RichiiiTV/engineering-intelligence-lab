# Getting started on Windows

## Prerequisites

- Python **3.12+** and `uv`.
- Node.js **22.12+** or **24**, with npm.
- A local Ollama service for model answers and semantic indexing.
- Docker Desktop with the Linux engine **only for PDF ingestion**; plain text,
  Markdown and code exports do not require the PDF worker.

```powershell
git clone https://github.com/RichiiiTV/engineering-intelligence-lab.git
cd engineering-intelligence-lab

uv sync --locked --extra dev
Copy-Item .env.example .env

# In your local Ollama installation:
ollama pull qwen3.5:4b-q8_0
ollama pull embeddinggemma:300m

Push-Location frontend
npm.cmd ci --ignore-scripts
npm.cmd run build
Pop-Location

uv run --locked uvicorn eil.api:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5
```

Open **http://127.0.0.1:8000/**. In a second terminal at the repository root:

```powershell
uv run --locked python -m eil.cli auth-bootstrap
```

Use the printed one-time setup code to create your administrator account. Choose
your own password; there are **no default credentials**. API documentation at
http://127.0.0.1:8000/docs requires sign-in too.

The backend serves the built frontend. Only one API worker/service may own a
state directory. Keep the application bound to loopback; network deployment is
outside its validated scope.

## Configure models and PDFs

`.env.example` documents the Ollama URL, generation model, embedding model and
optional local state directory. `.env`, model files, runtime databases, uploaded
material, local reports and dependencies are excluded from Git.
The defaults use [Qwen 3.5 4B Q8_0](https://ollama.com/library/qwen3.5:4b-q8_0)
and [EmbeddingGemma 300M](https://ollama.com/library/embeddinggemma:300m).

For PDF conversion, build the isolated worker and explicitly prefetch the required
Docling assets using the [operator guide](security-operations.md#isolated-pdf-conversion).
The Windows launcher, `scripts\start-workbench.cmd`, builds the UI and runs with
the optional document dependencies; it does not start Ollama or download models.
See the operator guide for the full container setup before uploading PDFs.

## Use it

**Administrator:** open **Administration → Machine knowledge / Maschinenwissen**.
Upload manuals, documentation or code exports and explicitly confirm publication
to active accounts in this workspace. Watch the ingestion progress and inspect
assignment evidence. Archive obsolete or inappropriate sources.

**User:** describe the fault and optionally attach an image or log. The backbone
handles machine matching, retrieval and conversation context. Users do not need
to select machines, notebooks or documents. Open a new chat for a different problem.

Example questions:

> Mein Voron 2.4 hat Probleme mit der ersten Schicht. Welche Symptome nennt die
> Dokumentation für eine schlecht ausgerichtete Gantry? Bitte mit Quellen.

> My machine uses a Siemens S7-1500 and shows diagnostic code 16#80A1.
> What public documentation is available for this code?

Use **Sprache / Language** to switch the interface and the language of new answers.
Existing answers and source text are not rewritten. Open a citation to inspect
its saved passage, original excerpt and document details.

### Included real-machine reference pack

The repository includes a pinned **Voron 2.4** public reference pack: official
product information, V2 Gantry Squaring documentation and an Octopus controller
configuration. Original snapshots, attribution, hashes and full upstream GPLv3
license notices are retained.

On a new installation, import the combined Markdown file through the administrator
workflow; the existing local workspace's published catalog is not part of Git.
[Import instructions, sources and pilot results](public-machine-pilot.md).
Three generated CC0 reference guides are also bundled as educational fixtures.

## Development and verification

Run the backend on port 8000 and `npm.cmd run dev` in `frontend/`.
Vite serves http://127.0.0.1:5173/ and proxies `/api` to the backend.
The loopback app serves the production build; rebuild it after frontend changes.

```powershell
uv sync --locked --extra dev --extra hosted --extra inference
uv run --locked ruff check backend/src/eil tests scripts/model_manifest.py scripts/hpc_profiles.py
uv run --locked ruff format --check backend/src/eil tests scripts/model_manifest.py scripts/hpc_profiles.py
uv run --locked pytest -q
uv run --locked python -m eil.publication --history
uv run --locked python -m eil.supply_chain

Push-Location frontend
npm.cmd ci --ignore-scripts
npm.cmd test
npm.cmd run build
npm.cmd audit --audit-level=low
npm.cmd audit signatures
Pop-Location
```

The optional hosted adapter is installed for offline compatibility tests. Installing
it does not enable or authorize paid model runs. Those require an explicit provider,
model and operator credentials; the hosted quality comparison remains deferred.
Dependency lifecycle hooks are disabled by `frontend/.npmrc`. Repository test/build
scripts still run when explicitly invoked. Review dependency updates, including any
new install hook, before changing that policy.

See the [current project review](project-review-2026-11-01.md) for checked versions,
security findings, performance observations and remaining validation limits.
See [Linux/HPC setup](linux-hpc.md) for Bash launchers, the site's Ollama module
and the optional separately installed native vLLM server. The `inference` extra
installs the client only and does not start a model service.
