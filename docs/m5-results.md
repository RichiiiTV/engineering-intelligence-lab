# M5 implementation and validation

The user authorized M5 on 2026-10-29. Version 0.5.0 adds the synthetic benchmark,
local spans, bounded compiled-subagent experiment and optional hosted adapter.
The implementation stays separate from user cases and leaves the workbench on
single-agent Ollama. No later milestone or production integration was started.

The final benchmark baseline is recorded after freezing the implementation.
See `m5-evaluation.md` for reproduction, scoring definitions, limits and official
compatibility sources. A live hosted comparison cannot be completed in this
environment because both OPENAI_API_KEY and a hosted model selection are absent.
Its slots must remain unrun, rather than becoming fake provider results.

## Validation before the final live matrix

- `uv lock` and `uv sync --locked --extra dev --extra documents --extra hosted`
  resolved version 0.5.0 and 184 lockfile packages.
- `uv run pytest -q`: 148 backend tests passed.
- `npm.cmd test -- --run`: 18 frontend tests passed.
- `npm.cmd run build`: TypeScript and Vite production build passed.
- `npx.cmd prettier --check src`: passed.
- The three owned PDFs were parsed with actual offline Docling 2.144.0 assets;
  all six rendered pages were visually inspected. Ordinary benchmark runs use
  those captured, hash-checked normalizations.
- Hosted adapter tests used the actual OpenAI SDK with a mocked HTTP transport:
  official endpoint, no automatic retries, `store=False`, actual serialized
  output cap, usage settlement, truncation and rate-limit failure checks.
- Delegation checks use real framework graphs and shared SQLite checkpoints,
  validate actual read-only catalogs, case isolation, cumulative counters and
  hard termination of a blocked child. Seeded incorrect claims fail the gates.

The first development matrix identified strict JSON-format failures and a
coordinator instruction conflict. Format failures remain failures; claim metrics
are now reported separately. The coordinator no longer receives instructions to
call case tools that are available only to its analyst. Development artifacts
remain under ignored `reports/m5-matrix-v1`; they are not the final baseline.
