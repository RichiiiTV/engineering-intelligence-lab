# Run from PowerShell inside the project directory, after installing uv.
uv sync --extra dev
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
uv run ruff check .
if ($LASTEXITCODE -ne 0) { throw "Lint checks failed" }
uv run ruff format --check .
if ($LASTEXITCODE -ne 0) { throw "Format checks failed" }
uv run pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
uv run python -m eil.cli demo
