import io
import json

import pytest

from eil import cli
from eil.agent import ModelUnavailableError


def test_cli_model_failure_has_no_traceback(monkeypatch, capsys):
    def unavailable(question):
        raise ModelUnavailableError("Start Ollama and select an installed model.")

    monkeypatch.setattr(cli, "run_agent", unavailable)
    monkeypatch.setattr("sys.argv", ["eil", "agent"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert "Start Ollama" in stderr
    assert "Traceback" not in stderr


def test_cli_unicode_answer_survives_windows_redirected_output(monkeypatch):
    result = {"answer": "S03: Δ 12.5021 pp → inspect lighting ✓"}
    monkeypatch.setattr(cli, "run_agent", lambda question: result)
    monkeypatch.setattr("sys.argv", ["eil", "agent"])
    buffer = io.BytesIO()
    output = io.TextIOWrapper(buffer, encoding="cp1252", write_through=True)
    monkeypatch.setattr("sys.stdout", output)
    cli.main()
    assert json.loads(buffer.getvalue().decode("cp1252")) == result
