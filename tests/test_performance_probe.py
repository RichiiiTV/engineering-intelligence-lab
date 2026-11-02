import json
import time

import httpx
import pytest

from eil import performance_probe as probe


def stalled_worker(output, pipe):
    time.sleep(30)


def test_plan_does_not_access_network_or_create_output(tmp_path, monkeypatch, capsys):
    def deny(*args, **kwargs):
        raise AssertionError("Plan-only mode must not use the model service")

    monkeypatch.setattr(httpx.Client, "send", deny)
    output = tmp_path / "not-created"
    assert probe.main(["--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "plan-only"
    assert not output.exists()


def test_metric_allowlist_and_distinct_decode_denominator():
    values = probe.metrics(
        {
            "total_duration": 10_000_000_000,
            "eval_count": 20,
            "eval_duration": 2_000_000_000,
            "prompt_eval_count": 100,
            "prompt_eval_duration": 1_000_000_000,
            "load_duration": -1,
            "private_text": "do not copy",
        }
    )
    assert values["decode_tokens_per_second"] == 10
    assert values["prefill_tokens_per_second"] == 100
    assert "load_duration" not in values and "private_text" not in values
    assert probe.metrics({"eval_count": True, "eval_duration": 0}) == {"eval_duration": 0}


def test_generated_quality_is_strict_and_separate_from_timing():
    expected = probe.FIXTURES[0]["expected"]
    assert probe.score(json.dumps(expected), expected)["passed"]
    assert not probe.score("```json\n" + json.dumps(expected) + "\n```", expected)["passed"]
    assert not probe.score(json.dumps(expected | {"extra": True}), expected)["passed"]
    assert not probe.score(
        '{"alarm":"SYNTH-E17","defekt_bewiesen":0}', probe.FIXTURES[1]["expected"]
    )["passed"]


def test_generation_is_bounded_and_does_not_keep_thinking_or_prompt_metadata():
    fixture = probe.FIXTURES[0]
    final = {
        "message": {"content": "", "thinking": "not collected"},
        "done": True,
        "done_reason": "stop",
        "eval_count": 20,
        "eval_duration": 1_000_000_000,
        "prompt_eval_count": 100,
        "prompt_eval_duration": 2_000_000_000,
    }

    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert body["options"] == {"temperature": 0, "num_ctx": 2048, "num_predict": 128}
        assert body["think"] is False and body["stream"] is True
        wire = json.dumps({"message": {"content": json.dumps(fixture["expected"])}}) + "\n"
        return httpx.Response(200, content=wire + json.dumps(final))

    with httpx.Client(
        base_url="http://localhost:11434", transport=httpx.MockTransport(handler)
    ) as client:
        budget = probe.Budget()
        row = probe.generate(client, budget, probe.MODELS[0], fixture)
    assert row["quality"]["passed"] and row["time_to_first_output_ms"] is not None
    assert row["provider_metrics"]["decode_tokens_per_second"] == 20
    assert budget.calls["generation"] == 1
    assert "not collected" not in json.dumps(row) and "prompt" not in row


def test_generation_does_not_follow_redirects():
    requests = []

    def handler(request):
        requests.append(request.url.host)
        return httpx.Response(307, headers={"location": "https://external.invalid/collect"})

    with (
        httpx.Client(
            base_url="http://localhost:11434",
            follow_redirects=False,
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        probe.generate(client, probe.Budget(), probe.MODELS[0], probe.FIXTURES[0])
    assert requests == ["localhost"]


def test_budget_refuses_calls_after_limits_or_deadline(monkeypatch):
    budget = probe.Budget()
    for _ in range(8):
        budget.admit("generation")
    with pytest.raises(probe.ProbeError, match="call_limit"):
        budget.admit("generation")
    monkeypatch.setattr(probe.time, "monotonic", lambda: budget.deadline + 1)
    with pytest.raises(probe.ProbeError, match="deadline"):
        budget.admit("embedding")


def test_oversized_or_incomplete_generation_fails_closed(monkeypatch):
    monkeypatch.setattr(probe, "MAX_BYTES", 128)
    for content, error in (
        (b"x" * 129, "response_too_large"),
        (b"{}\n", "missing_stream_completion"),
    ):
        with (
            httpx.Client(
                base_url="http://localhost:11434",
                transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content)),
            ) as client,
            pytest.raises(probe.ProbeError, match=error),
        ):
            probe.generate(client, probe.Budget(), probe.MODELS[0], probe.FIXTURES[0])


def test_output_outside_reports_and_existing_output_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="reports"):
        probe.run_probe(tmp_path / "elsewhere")
    output = tmp_path / "reports/existing"
    output.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        probe.run_probe(output)


def test_full_mock_probe_has_exact_finite_request_plan_and_immutable_output(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(
        probe,
        "verify_private_model",
        lambda base_url, model: {"digest": "a" * 64, "details": {"quantization_level": "TEST"}},
    )
    original = httpx.Client
    requests = []

    def handler(request):
        requests.append(request.url.path)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "test"})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        body = json.loads(request.content)
        if request.url.path == "/api/generate":
            assert body == {"model": body["model"], "keep_alive": "0s"}
            return httpx.Response(200, json={"done": True})
        if request.url.path == "/api/embed":
            assert body["input"] == [probe.EMBEDDING_TEXT] and body["truncate"] is False
            return httpx.Response(200, json={"embeddings": [[0.25] * 64]})
        fixture = next(f for f in probe.FIXTURES if f["prompt"] == body["messages"][0]["content"])
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "message": {"content": json.dumps(fixture["expected"])},
                    "done": True,
                    "eval_count": 18,
                }
            ),
        )

    monkeypatch.setattr(
        "httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    output = tmp_path / "reports/probe"
    card = probe.run_probe(output)
    assert card["completed"] and all(r["quality"]["passed"] for r in card["generation"])
    assert card["calls"] == {"generation": 8, "embedding": 4, "control": 9}
    assert card["embedding_vectors_identical"]
    assert len(requests) == 23
    assert json.loads((output / "scorecard.json").read_text()) == card
    with pytest.raises(FileExistsError):
        probe.run_probe(output)


def test_hard_supervisor_terminates_a_stalled_worker_and_preserves_unknown_outcome(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "MAX_SECONDS", 0.1)
    monkeypatch.setattr(probe, "_probe_child", stalled_worker)
    started = time.monotonic()
    card = probe.supervised_probe(tmp_path / "reports/stalled")
    assert time.monotonic() - started < 5
    assert not card["completed"]
    assert card["errors"][0]["code"] == "probe_worker_deadline_or_exit"
    assert "Unknown partial outcomes" in card["outcome"]
    assert json.loads((tmp_path / "reports/stalled/supervisor-error.json").read_text()) == card


def test_contention_mode_is_plan_only_without_live_flag(monkeypatch, capsys):
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: pytest.fail("Unexpected network"))
    assert probe.main(["--contention"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "plan-only" and plan["context_tokens"] == 8192
    assert plan["max_generation_calls"] == 4


def test_contention_records_real_residency_policy_difference_with_fixed_workbench_context(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "verify_private_model", lambda *a: {"digest": "a" * 64})
    original = httpx.Client
    loaded = {probe.MODELS[1]: {"name": probe.MODELS[1], "size": 1000, "size_vram": 1000}}

    def handler(request):
        path = request.url.path
        if path == "/api/version":
            return httpx.Response(200, json={"version": "test"})
        if path == "/api/ps":
            return httpx.Response(200, json={"models": list(loaded.values())})
        body = json.loads(request.content)
        if path == "/api/generate":
            assert "prompt" not in body and "messages" not in body
            loaded.pop(body["model"], None)
            return httpx.Response(200, json={"done": True})
        if path == "/api/embed":
            assert body["input"] == [probe.EMBEDDING_TEXT]
            if body["keep_alive"] == "30s":
                loaded[probe.EMBEDDING_MODEL] = {
                    "name": probe.EMBEDDING_MODEL,
                    "size": 100,
                    "size_vram": 100,
                }
            else:
                loaded.pop(probe.EMBEDDING_MODEL, None)
            return httpx.Response(200, json={"embeddings": [[0.25] * 64]})
        assert path == "/api/chat" and body["options"]["num_ctx"] == 8192
        assert body["options"]["num_predict"] == 128
        assert body["messages"][0]["content"] == probe.FIXTURES[0]["prompt"]
        loaded[probe.MODELS[0]] = {"name": probe.MODELS[0], "size": 1000, "size_vram": 1000}
        return httpx.Response(
            200,
            content=json.dumps(
                {"done": True, "message": {"content": json.dumps(probe.FIXTURES[0]["expected"])}}
            ),
        )

    monkeypatch.setattr(
        "httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    card = probe.run_contention(tmp_path / "reports/contention")
    assert card["completed"] and card["embedding_vectors_identical"]
    assert card["calls"] == {"generation": 4, "embedding": 4, "control": 7}
    assert not loaded
    unloaded, warm = card["policies"]
    assert unloaded["keep_alive"] == "0s" and warm["keep_alive"] == "30s"
    assert unloaded["before_generation"]["sum_model_vram_bytes"] == 1000
    assert warm["before_generation"]["sum_model_vram_bytes"] == 1100
    assert warm["after_generation"]["sum_model_vram_bytes"] == 1100


def test_residency_refuses_to_unload_unrelated_models():
    with (
        httpx.Client(
            base_url="http://localhost:11434",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"models": [{"name": "unrelated-private-model"}]}
                )
            ),
        ) as client,
        pytest.raises(probe.ProbeError, match="idle_window"),
    ):
        probe.residency(client, probe.Budget())


@pytest.mark.parametrize("remote", ["external-url", "cloud-alias"])
def test_live_preflight_rejects_remote_endpoint_and_cloud_alias_before_prompt(
    tmp_path, monkeypatch, remote
):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    requests = []
    original = httpx.Client

    def handler(request):
        requests.append(request)
        assert request.method == "GET" and not request.content
        return httpx.Response(
            200, json={"models": [{"name": probe.MODELS[0], "remote_model": "cloud"}]}
        )

    monkeypatch.setattr(
        "httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    if remote == "external-url":
        monkeypatch.setattr(probe, "OLLAMA_BASE_URL", "https://external.invalid")
    card = probe.run_probe(tmp_path / "reports/probe")
    assert not card["completed"] and card["errors"]
    assert card["calls"] == {"generation": 0, "embedding": 0, "control": 0}
    assert len(requests) == (0 if remote == "external-url" else 1)
