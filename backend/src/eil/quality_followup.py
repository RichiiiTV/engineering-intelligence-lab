"""Versioned public-corpus quality follow-up; original pilot artifacts stay immutable."""

import argparse
import hashlib
import json
import re
import time

from .agent import verify_private_model
from .catalog import Assignment, CatalogStore
from .knowledge import KnowledgeStore
from .performance_probe import MODELS, checked_output
from .service import RunService
from .settings import OLLAMA_BASE_URL, ROOT
from .tracing import export_trace

VERSION = "eil-voron-quality-followup-v3"
SCORING_REVISION = 3
PACK = ROOT / "data/public-machine-packs/voron-2.4-v1"
PACK_HASH = "6f989695d5ffcdb31da80a42911d5daae069c2f3e065020519c119e88639144e"
CASES = (
    (
        "controller",
        "en",
        "My Voron 2.4 uses the Octopus example configuration. Which MCU and bootloader size does that example specify? Cite the document. Local only.",
    ),
    (
        "gantry",
        "de",
        "Mein Voron 2.4 hat Probleme mit der ersten Schicht. Welche drei Symptome nennt der V2 Gantry Squaring Guide? Nenne auch die englischen Originalbezeichnungen und Quellen. Nur lokal.",
    ),
    (
        "unknown",
        "de",
        "Mein Voron 2.4 zeigt EIL-UNKNOWN-9999. Was bedeutet dieser Code laut den bereitgestellten Dokumenten? Keine Bedeutung erfinden. Nur lokal.",
    ),
)


def pack_content():
    paths = [
        p for p in PACK.glob("*.md") if hashlib.sha256(p.read_bytes()).hexdigest() == PACK_HASH
    ]
    if len(paths) != 1:
        raise ValueError("Reviewed public pack bytes changed or are missing")
    return paths[0].read_bytes()


def prepare(directory):
    content = pack_content()
    catalog = CatalogStore(directory)
    inbox = catalog.inbox("generated-quality-admin")
    docs = KnowledgeStore(directory, machine_id=inbox, owner_id="generated-quality-admin")
    doc = docs.add(
        "voron-2.4-official-reference-pack.md",
        content,
        title="Voron 2.4 official reference pack",
        family="Voron 2.4",
        version="Pinned v1",
        license_note="GPL-3.0 upstream snapshots and full notices; see committed pack manifest",
        data_policy="licensed-public",
        actor="generated-quality-admin",
        publish=False,
    )
    docs.index(doc["id"])
    with catalog.evidence.connection() as conn:
        catalog.publish(
            conn,
            doc["id"],
            "generated-quality-admin",
            Assignment(
                identity="Voron 2.4",
                identity_kind="product_family",
                family="Voron 2.4",
                model="Voron 2.4",
                identity_evidence="Voron 2.4",
                confidence="high",
            ),
            [],
        )
    return doc["id"]


def score(case, run):
    answer = (run.get("result") or {}).get("answer", "")
    contract = (run.get("result") or {}).get("answer_contract", {})
    hits = (run.get("catalog_lookup") or {}).get("hits", []) + run.get("catalog_source_reads", [])
    observed = {h["citation_id"] for h in hits}
    cited = set(re.findall(r"\[(kb:[^\]]+)\]", answer))
    checks = {
        "completed": run["status"] == "completed",
        "no_external_lookup": not run.get("siemens"),
        "no_invented_vendor": "siemens" not in answer.casefold(),
        "citations_observed": bool(cited & observed) and not (cited - observed),
    }
    if case == "controller":
        checks["documented_controller"] = "stm32f446" in answer.casefold()
        checks["documented_bootloader"] = bool(re.search(r"\b32\s*ki?b\b", answer, re.I))
        checks["no_negated_expected_facts"] = not re.search(
            r"\b(?:not|nicht|kein\w*)\s+(?:an?\s+)?(?:STM32F446|32\s*ki?b)\b|\bSTM32F446\s+(?:is not|ist nicht)\b",
            answer,
            re.I,
        )
    elif case == "gantry":
        checks["documented_symptoms"] = all(
            re.search(pattern, answer, re.I) for pattern in (r"first.layer", r"z.belts", r"racked")
        )
    elif case == "unknown":
        checks["explicit_unknown"] = bool(
            re.search(
                r"nicht (?:definiert|dokumentiert|enthalten|gefunden|belegt|erwähnt)|keine.{0,100}(?:Bedeutung|Information|Dokumentation)|not (?:documented|found|present)",
                answer,
                re.I,
            )
        )
        checks["citations_observed"] = not (cited - observed)
    else:
        raise ValueError("Unknown fixed quality fixture")
    checks["contract_not_flagged"] = contract.get("outcome") not in {
        "needs_review",
        "not_completed",
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "claim_entailment": "not_verified",
        "scoring_revision": SCORING_REVISION,
        "manual_review_required": True,
        "scope": "fixed public corpus facts only",
    }


def run(output):
    output = checked_output(output)
    identities = {model: verify_private_model(OLLAMA_BASE_URL, model)["digest"] for model in MODELS}
    output.mkdir(parents=True)
    state = output / "state"
    prepare(state)
    records = []
    for model in MODELS:
        for case, language, question in CASES:
            runner = RunService(state)
            run = runner.submit(
                question,
                {
                    "max_steps": 25,
                    "max_model_calls": 5,
                    "max_tool_calls": 8,
                    "max_total_tokens": 32768,
                    "max_output_tokens": 1024,
                    "timeout_seconds": 120,
                },
                owner_id="generated-quality-member",
                chat_mode=True,
                automatic_catalog=True,
                language=language,
            )
            runner.store.change(run["id"], lambda row, conn: row.update(model=model))
            with runner:
                final = runner.wait(run["id"], timeout=135)
                records.append(
                    {
                        "case": case,
                        "model": model,
                        "digest": identities[model],
                        "run_id": run["id"],
                        "status": final["status"],
                        "score": score(case, final),
                        "tokens": final["tokens"],
                        "model_calls": final["model_calls"],
                        "trace": export_trace(runner.store, run["id"]),
                    }
                )
            card = {
                "suite": VERSION,
                "source_sha256": PACK_HASH,
                "records": records,
                "passed": all(r["score"]["passed"] for r in records),
                "prior_results": "Original Voron and M5 failures are unchanged; this is a new follow-up.",
            }
            (output / "scorecard.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
            print(
                json.dumps({"case": case, "model": model, "score": records[-1]["score"]}),
                flush=True,
            )
    return card


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--output", default=ROOT / "reports" / (VERSION + "-" + time.strftime("%Y%m%d-%H%M%S"))
    )
    args = parser.parse_args(argv)
    if not args.live:
        print(
            json.dumps(
                {
                    "suite": VERSION,
                    "mode": "plan-only",
                    "models": MODELS,
                    "questions": len(CASES),
                    "max_runs": 6,
                    "paid_providers": False,
                }
            )
        )
        return 0
    return int(not run(args.output)["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
