"""Run baseline analytics without an LLM or invoke the optional actual agent."""

import argparse
import json

from .agent import ModelUnavailableError, run_agent
from .analytics import provisional_report


def main():
    parser = argparse.ArgumentParser(description="Engineering Intelligence Lab")
    parser.add_argument("mode", choices=("demo", "agent"))
    parser.add_argument(
        "--question",
        default="Which station had the largest increase in false ejections? Use tool evidence and distinguish hypotheses from facts.",
    )
    args = parser.parse_args()
    try:
        result = provisional_report() if args.mode == "demo" else run_agent(args.question)
    except (ModelUnavailableError, ValueError) as exc:
        parser.exit(1, f"Investigation failed: {exc}\n")
    # Escaped JSON also works when Windows redirects stdout through a legacy code page.
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
