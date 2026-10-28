"""Controlled model for real graph/checkpoint/process integration tests."""

import json
import os
import time
import uuid

import httpx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_ollama import ChatOllama

from eil.execution import execute_run
from eil.runs import RunStore


class ControlledOllama(ChatOllama):
    directory: str
    run_id: str

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        store = RunStore(self.directory)
        run = store.get(self.run_id)
        humans = [m.content for m in messages if isinstance(m, HumanMessage)]
        assert humans == [run["question"]], "Duplicated question or cross-thread state leak"
        scenario = run["question"].split(":")[0]
        tools = [m for m in messages if isinstance(m, ToolMessage)]
        if scenario == "model_down":
            raise httpx.ConnectError("Controlled offline connection failure")
        if scenario == "hang" or (scenario == "resume" and tools and run["attempts"] == 1):
            store.event(self.run_id, "fake_blocked", {})
            time.sleep(60)
        if scenario == "loop" or not tools:
            name = "inspect_station" if scenario == "bad_station" else "compare_station_performance"
            args = (
                {"station_id": "../../secrets", "period": "baseline"}
                if scenario == "bad_station"
                else {}
            )
            answer = AIMessage(
                content="",
                tool_calls=[
                    {"name": name, "args": args, "id": str(uuid.uuid4()), "type": "tool_call"}
                ],
            )
        else:
            observation = json.loads(tools[-1].content)
            if scenario == "bad_station":
                assert "Unknown station" in observation["error"]
                answer = AIMessage(content="Invalid station rejected.")
            else:
                assert observation[0]["station_id"] == "S03"
                answer = AIMessage(
                    content=f"S03 +12.5021 pp, ROW-00003; hypothesis only. {humans[0]}"
                )
        answer.usage_metadata = {"input_tokens": 100, "output_tokens": 30, "total_tokens": 130}
        if scenario == "output_limit":
            answer.response_metadata = {"done_reason": "length"}
        return ChatResult(generations=[ChatGeneration(message=answer)])


def forbidden_http(*args, **kwargs):
    raise AssertionError("The offline worker attempted an HTTP request")


def crashing_worker(directory, run_id):
    os._exit(23)


def controlled_worker(directory, run_id):
    httpx.Client.send = forbidden_http
    httpx.AsyncClient.send = forbidden_http
    run = RunStore(directory).get(run_id)
    model = ControlledOllama(model=run["model"], directory=directory, run_id=run_id)
    execute_run(directory, run_id, model=model)


def wait_for_event(store, run_id, kind, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events = store.events(run_id)
        if any(e["type"] == kind for e in events):
            return events
        if store.get(run_id)["status"] not in {"queued", "running"}:
            raise AssertionError(store.get(run_id))
        time.sleep(0.03)
    raise AssertionError(f"Event {kind} did not arrive: {store.get(run_id)}")
