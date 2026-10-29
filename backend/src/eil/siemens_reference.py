"""Small reviewed public manual index. Metadata only; no remote page execution."""

import re

REVIEWED = "2026-10-29"
BASE = "https://docs.tia.siemens.cloud/r/"
REFERENCES = (
    {
        "id": "1500-cycle-v20",
        "family": "S7-1500",
        "tia_version": "V20",
        "edition": "06/2025",
        "language": "en-US",
        "title": "S7-1500 / ET 200MP: Cycle and response times",
        "path": "simatic_s7_1500_et_200mp_manual_collection_enus_20/comprehensive-information/cpu-function-manuals/cycle-and-response-times",
        "topics": ("ob1", "cycle", "cyclic", "response", "zyklus", "zykluszeit", "reaktionszeit"),
    },
    {
        "id": "1200-cpu-v20",
        "family": "S7-1200",
        "tia_version": "V20",
        "edition": "11/2024",
        "language": "en-US",
        "title": "STEP 7 V20: Functional description of S7-1200 CPUs",
        "path": "en-us/v20/functional-description-of-s7-1200-cpus-s7-1200",
        "topics": (
            "programming",
            "program",
            "ob1",
            "memory",
            "firmware",
            "programmierung",
            "speicher",
            "manual",
            "handbuch",
        ),
    },
    {
        "id": "1200-configuration-v20",
        "family": "S7-1200",
        "tia_version": "V20",
        "edition": "11/2024",
        "language": "en-US",
        "title": "S7-1200 V20: Device configuration",
        "path": "simatic_s7_1200_manual_collection_enus_20/device-configuration",
        "topics": (
            "configuration",
            "configure",
            "security",
            "umac",
            "access",
            "certificate",
            "konfiguration",
            "zugriff",
            "sicherheit",
            "zertifikat",
        ),
    },
    {
        "id": "1200-g2-v20",
        "family": "S7-1200 G2",
        "tia_version": "V20",
        "edition": "12/2024",
        "language": "en-US",
        "title": "S7-1200 G2 Programmable Logic Controller, V20",
        "path": "simatic_s7_1200_g2_manual_collection_enus_20",
        "topics": (
            "g2",
            "manual",
            "programming",
            "memory",
            "cycle",
            "handbuch",
            "programmierung",
            "speicher",
        ),
    },
)


def query_context(question, *, family="", cpu="", firmware="", tia_version=""):
    if family not in {"", "S7-1200", "S7-1200 G2", "S7-1500"}:
        raise ValueError("Choose a supported SIMATIC family")
    if not re.fullmatch(r"[A-Za-z0-9 ./+_-]{0,50}", cpu):
        raise ValueError("CPU must be a public model/order number of at most 50 characters")
    if firmware and not re.fullmatch(r"V?\d{1,2}\.\d{1,2}(?:\.\d{1,2})?", firmware):
        raise ValueError("Use a firmware version such as V3.1 or V4.7.1")
    if tia_version and not re.fullmatch(r"V(?:1[7-9]|2[0-1])", tia_version):
        raise ValueError("Select TIA Portal V17 through V21")
    context = {"family": family, "cpu": cpu, "firmware": firmware, "tia_version": tia_version}
    suffix = "; ".join(f"{k}={v}" for k, v in context.items() if v)
    outbound = " ".join(question.split()) + (" Product context: " + suffix if suffix else "")
    if not question.strip() or len(outbound) > 500:
        raise ValueError("The question and product context together must fit 500 characters")
    return outbound, context


def references(question, context):
    family = context.get("family", "")
    lower = question.lower()
    if not family:
        family = (
            "S7-1200 G2"
            if "s7-1200" in lower and "g2" in lower
            else "S7-1200"
            if "s7-1200" in lower
            else "S7-1500"
            if "s7-1500" in lower
            else ""
        )
    tokens = set(re.findall(r"[\w-]+", lower)) | set(re.findall(r"\w+", lower))
    # Explicit versions in free text cannot be silently treated as V20.
    mentioned = set(re.findall(r"\bv(?:1[7-9]|2[0-1])\b", lower))
    version = context.get("tia_version", "")
    result = []
    for record in REFERENCES:
        if record["family"] != family or (version and version != record["tia_version"]):
            continue
        if mentioned and mentioned != {record["tia_version"].lower()}:
            continue
        if tokens.intersection(record["topics"]):
            result.append(
                {k: v for k, v in record.items() if k not in {"path", "topics"}}
                | {
                    "url": BASE + record["path"],
                    "reviewed_at": REVIEWED,
                    "kind": "curated_manual",
                    "firmware_compatibility_verified": False,
                }
            )
    return result


def enrich(result, question, outbound, context):
    curated = references(question, context)
    return {
        **result,
        "question": question.strip(),
        "outbound_query": outbound,
        "product_context": context,
        "curated_references": curated,
        "technical_answer_verified": False,
        "coverage_status": "reviewed_manual_candidates" if curated else "no_reviewed_version_match",
        "version_notice": "No exact CPU/firmware compatibility has been established. Open the manual and check its validity section. No verified engineering answer is available.",
    }
