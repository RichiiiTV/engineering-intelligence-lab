"""Reproducible private-machine retrieval/contracts suite, separate from M5 baselines."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from .answer_contract import assess
from .code_sources import inspect
from .evidence import EvidenceNotFound
from .machines import MachineStore
from .runs import RunStore
from .settings import ROOT

PACK = ROOT / "data/benchmarks/eil-knowledge-v1"
MANIFEST_SHA256 = "fa6aba30f19a35b5318d1e2be3d43355fef12672ad831b4c5ce1472b694f995b"


def evaluate(directory, *, semantic=False):
    raw = (PACK / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError(
            "Benchmark manifest changed; review and version a new baseline before scoring"
        )
    manifest = json.loads(raw)
    machines = MachineStore(directory)
    machine = machines.create("benchmark", "Generated demo")
    documents = machines.documents(machine["id"], "benchmark")
    ids = {}
    for item in manifest["documents"]:
        content = (PACK / item["filename"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(
                "Benchmark fixture hash changed; review/version the fixture before scoring"
            )
        row = documents.add(
            item["filename"],
            content,
            title=item["title"],
            family="Generated fictional demo",
            version=item["version"],
            profile={"software_version": item["version"]},
            license_note=manifest["license"],
            data_policy="synthetic",
            actor="benchmark",
        )
        ids[item["filename"]] = row["id"]
        if semantic:
            documents.index(row["id"])
    allowed = list(ids.values())
    results = []
    for index, case in enumerate(manifest["cases"]):
        category = case["category"]
        passed = False
        if category in {"retrieval", "unknown", "applicability"}:
            lookup = documents.search(case["query"], allowed, product_context=case.get("profile"))
            hits = {h["id"] for h in lookup["hits"]}
            passed = not hits if category == "unknown" else ids[case["expected"]] in hits
            if category == "applicability":
                passed = (
                    passed
                    and ids[case["excluded"]] not in hits
                    and ids[case["excluded"]] in lookup["excluded_document_ids"]
                )
        elif category == "contract":
            hit = documents.search("INJECTION_CANARY", [ids["adversarial.md"]])["hits"][0]
            cid = hit["citation_id"]
            text = hit["text"]
            answers = {
                "observed": f"Fixture observation [{cid}]",
                "unseen": "Unsupported [kb:unseen:p1:c0]",
                "quote-match": f"> {text.splitlines()[0]}\n[{cid}]",
                "quote-mismatch": f"> Invented requirement that does not occur in any source.\n[{cid}]",
            }
            outcome = assess(
                {"machine_id": machine["id"], "machine_lookup": {"hits": [hit]}},
                answers[case["variant"]],
            )["outcome"]
            passed = outcome == (
                "needs_review"
                if case["variant"] in {"unseen", "quote-mismatch"}
                else "references_checked"
            )
        elif category == "static":
            if case["variant"] == "syntax":
                passed = bool(inspect("checks.py", (PACK / "checks.py").read_text())["findings"])
            else:
                sentinel = Path(directory) / "must-not-execute"
                inspect("test.py", f"open({str(sentinel)!r},'w').write('bad')")
                passed = not sentinel.exists()
        elif category == "isolation":
            try:
                if case["variant"] == "other-owner":
                    machines.documents(machine["id"], "outsider")
                else:
                    other = machines.create("benchmark", "Other machine")
                    machines.documents(other["id"], "benchmark").document(allowed[0])
            except EvidenceNotFound:
                passed = True
        elif category == "snapshot":
            runs = RunStore(directory)
            run = runs.create("ConveyorStopBand", owner_id="benchmark", machine_id=machine["id"])
            if case["variant"] == "archive-retained":
                documents.set_active(allowed[0], False)
                passed = (
                    documents.resolve(f"kb:{allowed[0]}:p1:c0", run["machine_document_ids"])["id"]
                    == allowed[0]
                )
                documents.set_active(allowed[0], True)
            else:
                extra = documents.add(
                    "later.txt",
                    b"Later generated source",
                    title="Later",
                    family="Demo",
                    version="V20",
                    license_note="CC0",
                    data_policy="synthetic",
                    actor="benchmark",
                )
                passed = extra["id"] not in run["machine_document_ids"]
        results.append({"id": index + 1, "category": category, "passed": passed})
    metrics = {
        category: {
            "passed": sum(r["passed"] for r in results if r["category"] == category),
            "total": sum(r["category"] == category for r in results),
        }
        for category in sorted({r["category"] for r in results})
    }
    return {
        "suite": manifest["id"],
        "manifest_sha256": hashlib.sha256((PACK / "manifest.json").read_bytes()).hexdigest(),
        "retrieval_mode": "local-hybrid" if semantic else "lexical-unindexed",
        "metrics": metrics,
        "passed": all(r["passed"] for r in results),
        "results": results,
        "limits": [
            "Generated closed-corpus smoke, not real-manual coverage.",
            "Citation/quotation checks do not establish general claim entailment.",
            "No LLM answer quality, prompt-injection resistance or hardware correctness score.",
            "Hosted validation deferred; existing M5 baselines unchanged.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--semantic", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="eil-knowledge-eval-") as directory:
        report = evaluate(directory, semantic=args.semantic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["suite", "retrieval_mode", "passed", "metrics"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
