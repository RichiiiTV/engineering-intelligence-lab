"""Execute the existing graph with durable checkpoints and budget/audit hooks."""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar

import httpx
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import GraphRecursionError
from ollama import ResponseError

from .agent import MODEL_CONTEXT_TOKENS, ModelUnavailableError, build_agent
from .runs import BudgetExceeded, RunStopped, RunStore

_parent_span = ContextVar("eil_parent_span", default=None)


class RunMiddleware(AgentMiddleware):
    def __init__(self, store, run_id, agent_name="investigator"):
        self.store, self.run_id = store, run_id
        self.agent_name = agent_name

    def span(self):
        return {
            "span_id": str(uuid.uuid4()),
            "parent_span_id": _parent_span.get(),
            "agent": self.agent_name,
        }

    def wrap_model_call(self, request, handler):
        run, admission = self.store.reserve_model(self.run_id, MODEL_CONTEXT_TOKENS)
        reserved = admission["reserved"]
        finalizing = admission["finalizing"]
        if finalizing:
            system = request.system_message.text if request.system_message else ""
            request = request.override(
                tools=[],
                tool_choice=None,
                model_settings={**request.model_settings, "reasoning": False},
                system_message=SystemMessage(
                    content=system
                    + "\nCAPACITY SUMMARY: Finish now using only evidence already gathered. Do not call any more tools. Return a concise useful answer with exact source citations. State missing evidence and uncertainty, and do not imply that unperformed checks succeeded. This is a bounded summary, not proof of cause."
                ),
            )
        span = self.span()
        self.store.event(
            self.run_id,
            "model_started",
            {
                **span,
                "reserved_tokens": reserved,
                "output_tokens": admission["output_tokens"],
                "finalizing": finalizing,
            },
        )
        started = time.perf_counter()
        try:
            from .providers import cap_request

            request = cap_request(request, admission["output_tokens"])
            response = handler(request)
        except Exception as exc:
            self.store.event(
                self.run_id,
                "model_failed",
                {
                    **span,
                    "error_type": type(exc).__name__,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )
            raise
        # Missing usage is conservatively charged as the whole reservation.
        usage = [getattr(m, "usage_metadata", None) for m in response.result]
        actual = sum(u["total_tokens"] for u in usage) if usage and all(usage) else reserved
        self.store.settle_tokens(self.run_id, reserved, actual)
        self.store.charge(self.run_id, "model_calls", 0)
        self.store.event(
            self.run_id,
            "model_finished",
            {
                **span,
                "tokens": actual,
                "usage_known": bool(usage and all(usage)),
                "input_tokens": sum(u["input_tokens"] for u in usage)
                if usage and all(usage)
                else None,
                "output_tokens": sum(u["output_tokens"] for u in usage)
                if usage and all(usage)
                else None,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        if any(
            (
                getattr(m, "response_metadata", {}).get("done_reason")
                or getattr(m, "response_metadata", {}).get("finish_reason")
            )
            in {"length", "max_tokens"}
            for m in response.result
        ):
            raise BudgetExceeded("Model output limit reached before completion", "output_tokens")
        if finalizing:
            if any(getattr(m, "tool_calls", []) for m in response.result):
                raise BudgetExceeded(
                    "The model requested more tools instead of finishing its bounded summary",
                    "model_calls",
                )
            self.store.change(self.run_id, lambda r, c: r.update(budget_summary=True))
        for message in response.result:
            for call in getattr(message, "tool_calls", []):
                self.store.event(
                    self.run_id,
                    "tool_requested",
                    {
                        "name": call["name"],
                        "arguments": call["args"],
                        "tool_call_id": call["id"],
                        "agent": self.agent_name,
                    },
                )
        return response

    def wrap_tool_call(self, request, handler):
        self.store.charge(self.run_id, "tool_calls")
        call = request.tool_call
        span = self.span()
        self.store.event(
            self.run_id, "tool_started", {**span, "name": call["name"], "tool_call_id": call["id"]}
        )
        parent = _parent_span.set(span["span_id"])
        started = time.perf_counter()
        try:
            result = handler(request)
        except Exception as exc:
            self.store.event(
                self.run_id,
                "tool_failed",
                {
                    **span,
                    "name": call["name"],
                    "tool_call_id": call["id"],
                    "error_type": type(exc).__name__,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )
            raise
        finally:
            _parent_span.reset(parent)
        # A framework delegation returns a Command, not a ToolMessage. Record
        # only its returned answer, never the entire child state/reasoning.
        observation = getattr(result, "content", None)
        if observation is None and isinstance(getattr(result, "update", None), dict):
            observation = "\n".join(m.text for m in result.update.get("messages", []))
        self.store.event(
            self.run_id,
            "tool_finished",
            {
                **span,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "name": call["name"],
                "tool_call_id": call["id"],
                "status": getattr(result, "status", "success"),
                "observation": observation if observation is not None else str(result),
            },
        )
        return result


def execute_run(directory, run_id, *, model=None, agent_mode="single"):
    """Trusted worker entry; `model` injection is for offline tests, never an API input."""
    store = RunStore(directory)
    run = store.get(run_id)
    config = {
        "configurable": {"thread_id": run["thread_id"]},
        "recursion_limit": max(1, run["limits"]["max_steps"] - run["steps"]),
    }
    try:
        if agent_mode not in {"single", "delegated"}:
            raise ValueError("Unknown agent experiment")
        with SqliteSaver.from_conn_string(str(store.directory / "checkpoints.sqlite3")) as saver:
            evidence_tools = None
            if run.get("case_id"):
                from .case_tools import case_tools

                evidence_tools = case_tools(store.directory, run["case_id"], run["source_ids"])
                if run.get("use_mock_mcp", False):
                    from .mock_mcp import read_mock_station_context

                    evidence_tools.append(read_mock_station_context)
            common = dict(
                model=model,
                evidence_tools=evidence_tools,
                model_options={
                    "model_name": run["model"],
                    "base_url": run["base_url"],
                    "max_output_tokens": run["limits"]["max_output_tokens"],
                },
            )
            subagents = []
            if agent_mode == "delegated":
                if not evidence_tools or model is None:
                    raise ValueError(
                        "Delegation requires explicit benchmark model and case evidence"
                    )
                child = build_agent(
                    **common,
                    checkpointer=saver,
                    middleware=[RunMiddleware(store, run_id, "evidence-analyst")],
                )
                subagents = [
                    {
                        "name": "evidence-analyst",
                        "description": "Read the uploaded case evidence, compare CSV stations, search PDFs, and return concise findings with exact citations and uncertainty.",
                        "runnable": child,
                    }
                ]
                common["evidence_tools"] = []
            graph = build_agent(
                **common,
                checkpointer=saver,
                middleware=[RunMiddleware(store, run_id)],
                subagents=subagents,
                # Deep Agents requires read_file scaffolding, even for the
                # coordinator. Its StateBackend is empty and virtual.
                filesystem_tools=("read_file",)
                if subagents
                else ("ls", "read_file", "glob", "grep"),
                extra_prompt=(
                    "\nYou are the coordinator. Delegate the entire question once using task with subagent_type='evidence-analyst'. Then summarize its findings, preserving exact source citations and uncertainty. Do not repeat the delegation. You have no case evidence tools yourself."
                    if subagents
                    else ""
                ),
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
                for namespace, update in graph.stream(
                    payload, config=config, stream_mode="updates", durability="sync", subgraphs=True
                ):
                    store.charge(run_id, "steps")
                    store.event(
                        run_id, "checkpoint", {"nodes": list(update), "namespace": list(namespace)}
                    )
            state = graph.get_state(config).values
            last = state["messages"][-1]
            if getattr(last, "type", None) != "ai" or getattr(last, "tool_calls", []):
                raise RuntimeError("Graph ended without a final answer")
            store.finish(
                run_id,
                "completed",
                result={
                    "answer": last.content,
                    "capacity_limited": bool(store.get(run_id).get("budget_summary")),
                    "warning": "Experimental local LLM output; verify metrics against tool results."
                    + (
                        " A bounded summary uses only the evidence gathered so far; further checks may be needed."
                        if store.get(run_id).get("budget_summary")
                        else ""
                    ),
                },
            )
    except RunStopped:
        # The supervisor owns the final pause/cancel transition and the process lifetime.
        return
    except (BudgetExceeded, GraphRecursionError) as exc:
        message = str(exc) if isinstance(exc, BudgetExceeded) else "Graph step budget exhausted"
        store.finish(
            run_id,
            "budget_exceeded",
            error={
                "code": "budget_exceeded",
                "message": message,
                "resource": getattr(exc, "resource", None),
            },
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
