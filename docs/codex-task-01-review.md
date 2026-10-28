# First Codex session — audit the foundation before adding features

Read `AGENTS.md`, `README.md`, `docs/architecture.md`, and `docs/roadmap.md`.

The repository was scaffolded with deterministic synthetic-data analytics and an **unverified** Deep Agents/Ollama integration. Your first job is to validate the foundation on the user's Windows setup, NOT immediately build a frontend or a large agent system.

1. Run `uv sync --extra dev` and commit a tested `uv.lock` after resolving compatibility using official package documentation.
2. Run `uv run pytest -q`, `uv run python -m eil.cli demo`, and start FastAPI; document the results.
3. Review the `create_deep_agent` / `ChatOllama` integration against installed versions. Fix API incompatibilities and write offline unit tests using mocks or stub models.
4. Add robust local-model connectivity errors and a manual `uv run python -m eil.cli agent` smoke test. Run smoke test only if Ollama and the configured model are available. Do not substitute a paid provider automatically.
5. Review the agent's accessible built-in tools. Ensure host shell, arbitrary code execution, and unrestricted filesystem access remain unavailable.
6. Add `ruff` checks, update README and tests as needed.
7. Summarize real test results and all unverified integration behaviors. Then STOP; do not start M2 until this review is complete.

Acceptance: reproducible environment, tests passing, offline fake-model integration test, no unreviewed agent permissions, realistic Ollama limitations documented.
