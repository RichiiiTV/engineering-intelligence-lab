"""Offline npm lock policy; advisory/signature checks remain separate CI gates."""

import base64
import binascii
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
REVIEWED_LIFECYCLES = {"esbuild", "fsevents"}


def validate_lock(lock):
    findings = []
    if lock.get("lockfileVersion") != 3 or not isinstance(lock.get("packages"), dict):
        return ["Expected an npm v3 lockfile with explicit package records"]
    for path, package in lock["packages"].items():
        if not path:
            continue
        name = package.get("name") or path.rsplit("node_modules/", 1)[-1]
        try:
            url = urlsplit(package.get("resolved", ""))
            approved = (
                url.scheme == "https"
                and url.hostname == "registry.npmjs.org"
                and url.port in {None, 443}
                and not (url.username or url.password or url.query or url.fragment)
            )
        except ValueError:
            approved = False
        if not approved or package.get("link"):
            findings.append(f"{name}: dependency must use the public HTTPS npm registry")
        integrity = package.get("integrity", "")
        try:
            valid = (
                integrity.startswith("sha512-")
                and len(base64.b64decode(integrity[7:], validate=True)) == 64
            )
        except (ValueError, binascii.Error):
            valid = False
        if not valid:
            findings.append(f"{name}: expected a complete SHA-512 integrity pin")
        if package.get("hasInstallScript") and name not in REVIEWED_LIFECYCLES:
            findings.append(f"{name}: new install hook requires explicit review")
    return findings


def main():
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    findings = validate_lock(lock)
    for finding in findings:
        print(finding)
    print(
        f"Checked {len(lock.get('packages', {})) - 1} locked npm entries; {len(findings)} findings."
    )
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
