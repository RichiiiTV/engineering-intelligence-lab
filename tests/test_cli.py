import io
import json

import pytest

from eil import cli
from eil.agent import ModelUnavailableError
from eil.evidence import EvidenceNotFound


def test_cli_model_failure_has_no_traceback(monkeypatch, capsys):
    def unavailable(question, limits):
        raise ModelUnavailableError("Start Ollama and select an installed model.")

    monkeypatch.setattr(cli, "_run_local", unavailable)
    monkeypatch.setattr("sys.argv", ["eil", "agent"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert "Start Ollama" in stderr
    assert "Traceback" not in stderr


def test_cli_unknown_case_is_actionable_without_traceback(monkeypatch, capsys):
    def missing(question, limits, *, case_id):
        raise EvidenceNotFound("Case not found")

    monkeypatch.setattr(cli, "_run_local", missing)
    monkeypatch.setattr("sys.argv", ["eil", "agent", "--case-id", "unknown"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    text = capsys.readouterr().err
    assert "Case not found" in text and "Traceback" not in text


def test_cli_unicode_answer_survives_windows_redirected_output(monkeypatch):
    result = {"status": "completed", "result": {"answer": "S03: Δ 12.5021 pp → inspect lighting ✓"}}
    monkeypatch.setattr(cli, "_run_local", lambda question, limits: result)
    monkeypatch.setattr("sys.argv", ["eil", "agent"])
    buffer = io.BytesIO()
    output = io.TextIOWrapper(buffer, encoding="cp1252", write_through=True)
    monkeypatch.setattr("sys.stdout", output)
    cli.main()
    assert json.loads(buffer.getvalue().decode("cp1252")) == result
