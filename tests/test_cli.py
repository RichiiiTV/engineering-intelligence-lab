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
