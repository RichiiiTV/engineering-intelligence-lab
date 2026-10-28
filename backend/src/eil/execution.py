"""Execute the existing graph with durable checkpoints and budget/audit hooks."""

from __future__ import annotations

import httpx
from langchain.agents.middleware import AgentMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import GraphRecursionError
from ollama import ResponseError

from .agent import MODEL_CONTEXT_TOKENS, ModelUnavailableError, build_agent
from .runs import BudgetExceeded, RunStopped, RunStore


class RunMiddleware(AgentMiddleware):
    def __init__(self, store, run_id):
        self.store, self.run_id = store, run_id

    def wrap_model_call(self, request, handler):
        run = self.store.charge(self.run_id, "model_calls")
        reserved = MODEL_CONTEXT_TOKENS + run["limits"]["max_output_tokens"]
        self.store.charge(self.run_id, "tokens", reserved)
        self.store.event(self.run_id, "model_started", {"reserved_tokens": reserved})
        response = handler(request)
        # Missing usage is conservatively charged as the whole reservation.
        usage = [getattr(m, "usage_metadata", None) for m in response.result]
        actual = sum(u["total_tokens"] for u in usage) if usage and all(usage) else reserved
        self.store.settle_tokens(self.run_id, reserved, actual)
        self.store.charge(self.run_id, "model_calls", 0)
        self.store.event(self.run_id, "model_finished", {"tokens": actual})
        if any(
            getattr(m, "response_metadata", {}).get("done_reason") in {"length", "max_tokens"}
            for m in response.result
        ):
            raise BudgetExceeded("Model output limit reached before completion")
        for message in response.result:
            for call in getattr(message, "tool_calls", []):
                self.store.event(
                    self.run_id,
                    "tool_requested",
                    {"name": call["name"], "arguments": call["args"], "tool_call_id": call["id"]},
                )
        return response

    def wrap_tool_call(self, request, handler):
        self.store.charge(self.run_id, "tool_calls")
        call = request.tool_call
        self.store.event(
            self.run_id, "tool_started", {"name": call["name"], "tool_call_id": call["id"]}
        )
        try:
            result = handler(request)
        except Exception as exc:
            self.store.event(
                self.run_id, "tool_failed", {"name": call["name"], "error_type": type(exc).__name__}
            )
            raise
        self.store.event(
            self.run_id,
            "tool_finished",
            {
                "name": call["name"],
                "tool_call_id": call["id"],
                "status": getattr(result, "status", "success"),
                "observation": getattr(result, "content", str(result)),
            },
        )
        return result


def execute_run(directory, run_id, *, model=None):
    """Trusted worker entry; `model` injection is for offline tests, never an API input."""
    store = RunStore(directory)
    run = store.get(run_id)
    config = {
        "configurable": {"thread_id": run["thread_id"]},
        "recursion_limit": max(1, run["limits"]["max_steps"] - run["steps"]),
    }
    try:
        with SqliteSaver.from_conn_string(str(store.directory / "checkpoints.sqlite3")) as saver:
            evidence_tools = None
            if run.get("case_id"):
                from .case_tools import case_tools

                evidence_tools = case_tools(store.directory, run["case_id"], run["source_ids"])
            graph = build_agent(
                model=model,
                checkpointer=saver,
                middleware=[RunMiddleware(store, run_id)],
                evidence_tools=evidence_tools,
                model_options={
                    "model_name": run["model"],
                    "base_url": run["base_url"],
                    "max_output_tokens": run["limits"]["max_output_tokens"],
                },
            )
            saved = graph.get_state(config)
            # Recover a checkpoint committed just before the worker was interrupted,
            # even if its corresponding run-record/event write did not happen yet.
            committed = max(0, (saved.metadata or {}).get("step", 0))
            used_steps = max(run["steps"], committed)
            store.change(run_id, lambda r, c: r.update(steps=used_steps))
            config["recursion_limit"] = max(1, run["limits"]["max_steps"] - used_steps)
            # None resumes pending nodes; never append the user's question a second time.
            payload = (
                None
                if saved.values
                else {"messages": [{"role": "user", "content": run["question"]}]}
            )
            if payload is not None or saved.next:
                if used_steps >= run["limits"]["max_steps"]:
                    raise BudgetExceeded("steps budget exhausted; create a new investigation")
                for update in graph.stream(
                    payload, config=config, stream_mode="updates", durability="sync"
                ):
                    store.charge(run_id, "steps")
                    store.event(run_id, "checkpoint", {"nodes": list(update)})
            state = graph.get_state(config).values
            last = state["messages"][-1]
            if getattr(last, "type", None) != "ai" or getattr(last, "tool_calls", []):
                raise RuntimeError("Graph ended without a final answer")
            store.finish(
                run_id,
                "completed",
                result={
                    "answer": last.content,
                    "warning": "Experimental local LLM output; verify metrics against tool results.",
                },
            )
    except RunStopped:
        # The supervisor owns the final pause/cancel transition and the process lifetime.
        return
    except (BudgetExceeded, GraphRecursionError) as exc:
        message = str(exc) if isinstance(exc, BudgetExceeded) else "Graph step budget exhausted"
        store.finish(
            run_id, "budget_exceeded", error={"code": "budget_exceeded", "message": message}
        )
    except (ModelUnavailableError, ConnectionError, httpx.RequestError, ResponseError) as exc:
        if isinstance(exc, ModelUnavailableError):
            message = str(exc)
        elif isinstance(exc, httpx.TimeoutException):
            message = "Ollama request timed out. Check model resources or choose a smaller model."
        elif isinstance(exc, ResponseError):
            message = (
                f"Ollama rejected the request (HTTP {exc.status_code}). Check the installed "
                "model, tool-calling support and available memory."
            )
        else:
            message = "Ollama connection failed. Start the service and check EIL_OLLAMA_BASE_URL."
        store.finish(run_id, "failed", error={"code": "model_unavailable", "message": message})
    except Exception as exc:
        store.finish(
            run_id,
            "failed",
            error={
                "code": "execution_error",
                "message": f"Investigation stopped ({type(exc).__name__}). Inspect events, then resume or create a new run.",
            },
        )
