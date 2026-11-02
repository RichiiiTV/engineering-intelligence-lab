"""Versioned public-corpus quality follow-up; original pilot artifacts stay immutable."""

import argparse
import hashlib
import json
import re
import time

from .agent import verify_private_model
from .answer_contract import assess
from .catalog import Assignment, CatalogStore
from .knowledge import KnowledgeStore
from .performance_probe import MODELS, checked_output
from .service import RunService
from .settings import OLLAMA_BASE_URL, ROOT, inference_config
from .tracing import export_trace

VERSION = "eil-voron-quality-followup-v9"
SCORING_REVISION = 9
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
        "no_unperformed_log_checks": not any(
            issue.startswith("Some investigation claims") for issue in assess(run, answer)["issues"]
        ),
    }
    if case == "controller":
        checks["documented_controller"] = "stm32f446" in answer.casefold()
        checks["documented_bootloader"] = bool(re.search(r"\b32\s*ki?b\b", answer, re.I))
        checks["literal_citation_support"] = not any(
            issue.startswith("Some technical identifiers")
            for issue in assess(run, answer)["issues"]
        )
        checks["no_negated_expected_facts"] = not re.search(
            r"\b(?:not|nicht|kein\w*)\s+(?:an?\s+)?(?:STM32F446|32\s*ki?b)\b|\bSTM32F446\s+(?:is not|ist nicht)\b",
            answer,
            re.I,
        )
    elif case == "gantry":
        checks["documented_symptoms"] = all(
            re.search(pattern, answer, re.I) for pattern in (r"first.layer", r"z.belts", r"racked")
        )
        checks["no_known_component_mistranslation"] = not re.search(
            r"Riemenscheib|eingerastet|verrastet", answer, re.I
        )
    elif case == "unknown":
        checks["explicit_unknown"] = bool(
            re.search(
                r"nicht (?:definiert|dokumentiert|enthalten|gefunden|belegt|erwähnt)|keine.{0,100}(?:Bedeutung|Information|Dokumentation)|kein Fehlercode.{0,100}erwähnt|not (?:documented|found|present)",
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


def targets(configured=False):
    if configured:
        return [inference_config()[0]]
    return [
        {
            "provider": "ollama",
            "base_url": OLLAMA_BASE_URL,
            "model_name": model,
            "revision": "",
            "vision": False,
        }
        for model in MODELS
    ]


def implementation_digest():
    digest = hashlib.sha256()
    for path in sorted((ROOT / "backend/src/eil").glob("*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def suite_summary(records, expected, stable):
    return {
        "complete": len(records) == expected,
        "implementation_stable": stable,
        "expected_runs": expected,
        "passed": len(records) == expected
        and stable
        and all(r["score"]["passed"] for r in records),
        "generated_answer_passes": sum(
            r["score"]["passed"] and r.get("answer_mode", "generated") == "generated"
            for r in records
        ),
        "source_extract_responses": sum(r.get("answer_mode") == "source_extract" for r in records),
    }


def run(output, *, configured=False):
    output = checked_output(output)
    revision = implementation_digest()
    selected = targets(configured)
    identities = {
        model["model_name"]: verify_private_model(
            model["base_url"],
            model["model_name"],
            provider=model["provider"],
            revision=model["revision"],
        )["digest"]
        for model in selected
    }
    output.mkdir(parents=True)
    state = output / "state"
    prepare(state)
    records = []
    for selected_model in selected:
        model = selected_model["model_name"]
        for case, language, question in CASES:
            if implementation_digest() != revision:
                raise ValueError(
                    "Implementation changed during quality evaluation; use a fresh output directory"
                )
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
            runner.store.change(
                run["id"],
                lambda row, conn: row.update(
                    model=model,
                    base_url=selected_model["base_url"],
                    model_provider=selected_model["provider"],
                    model_revision=selected_model["revision"],
                    model_vision=selected_model["vision"],
                ),
            )
            with runner:
                final = runner.wait(run["id"], timeout=135)
                records.append(
                    {
                        "case": case,
                        "model": model,
                        "provider": selected_model["provider"],
                        "answer_mode": (final.get("result") or {}).get("answer_mode", "generated"),
                        "draft_answer_contract": (final.get("result") or {}).get(
                            "draft_answer_contract"
                        ),
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
                "implementation_sha256": revision,
                **suite_summary(
                    records, len(selected) * len(CASES), implementation_digest() == revision
                ),
                "prior_results": "Original Voron and M5 failures are unchanged; this is a new follow-up.",
            }
            (output / "scorecard.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
            if not card["implementation_stable"]:
                raise ValueError(
                    "Implementation changed during quality evaluation; use a fresh output directory"
                )
            print(
                json.dumps({"case": case, "model": model, "score": records[-1]["score"]}),
                flush=True,
            )
    return card


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--configured",
        action="store_true",
        help="Evaluate the explicit local operator backend/model instead of the two baseline Ollama models",
    )
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
                    "models": [t["model_name"] for t in targets(args.configured)],
                    "questions": len(CASES),
                    "max_runs": len(CASES) * len(targets(args.configured)),
                    "paid_providers": False,
                }
            )
        )
        return 0
    return int(not run(args.output, configured=args.configured)["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
