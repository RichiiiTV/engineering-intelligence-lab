"""Run baseline analytics without an LLM or invoke the optional actual agent."""

import argparse
import json
import sys

from .agent import ModelUnavailableError
from .analytics import provisional_report
from .evidence import EvidenceConflict, EvidenceNotFound
from .runs import RunConflict, RunLimits, RunNotFound, RunStore
from .service import RunService
from .settings import STATE_DIR


def _run_local(question, limits, run_id=None, *, case_id=None):
    with RunService() as runner:
        run = (
            runner.store.control(run_id, "resume")
            if run_id
            else runner.submit(question, limits, case_id=case_id)
        )
        print(f"Investigation {run['id']}", file=sys.stderr)
        try:
            return runner.wait(run["id"])
        except KeyboardInterrupt:
            runner.store.control(run["id"], "cancel")
            return runner.wait(run["id"], timeout=5)


def main():
    parser = argparse.ArgumentParser(description="Engineering Intelligence Lab")
    parser.add_argument(
        "mode",
        choices=("demo", "agent", "status", "trace", "pause", "resume", "cancel", "auth-bootstrap"),
    )
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--case-id", help="Use this case's immutable uploaded-evidence snapshot")
    parser.add_argument(
        "--question",
        default="Which station had the largest increase in false ejections? Use tool evidence and distinguish hypotheses from facts.",
    )
    args = parser.parse_args()
    try:
        if args.mode == "demo":
            result = provisional_report()
        elif args.mode == "auth-bootstrap":
            from .auth import AuthStore

            result = {
                "bootstrap_code": AuthStore(STATE_DIR).bootstrap(),
                "expires_in_seconds": 900,
                "instructions": "Enter this one-time code on the local setup page. Do not share it or put it in a URL.",
            }
        elif args.mode == "agent":
            limits = RunLimits(timeout_seconds=args.timeout_seconds)
            result = (
                _run_local(args.question, limits, case_id=args.case_id)
                if args.case_id
                else _run_local(args.question, limits)
            )
        else:
            if not args.run_id:
                parser.error("This command requires an investigation ID")
            if args.mode == "resume":
                result = _run_local(None, None, args.run_id)
            else:
                store = RunStore(STATE_DIR)
                if args.mode == "trace":
                    from .tracing import export_trace

                    result = export_trace(store, args.run_id)
                else:
                    result = (
                        store.get(args.run_id)
                        if args.mode == "status"
                        else store.control(args.run_id, args.mode)
                    )
    except (
        ModelUnavailableError,
        RunConflict,
        RunNotFound,
        EvidenceConflict,
        EvidenceNotFound,
        ValueError,
        TimeoutError,
    ) as exc:
        parser.exit(1, f"Investigation failed: {exc}\n")
    # Escaped JSON also works when Windows redirects stdout through a legacy code page.
    print(json.dumps(result, indent=2))
    if args.mode in {"agent", "resume"} and result["status"] != "completed":
        parser.exit(130 if result["status"] == "cancelled" else 1)


if __name__ == "__main__":
    main()
