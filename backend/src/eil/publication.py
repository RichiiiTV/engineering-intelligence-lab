"""Trusted operator check for public Git content; never an agent tool."""

import argparse
import base64
import re
import subprocess
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIMIT = 20 * 1024 * 1024
EMAIL = re.compile(rb"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
HOME = re.compile(
    rb"(?i:[A-Z]:[/\\]Users[/\\])[^\s<>\"'/\\\[\]{}]+"
    rb"|(?<![a-z/])/Users/[^\s/<>\"'\[\]{}]+"
)
SECRET = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|"
    rb"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|"
    rb"\bsk-(?:proj-|ant-)?[A-Za-z0-9_\-]{30,}|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
)
PDF_STREAM = re.compile(rb"\bstream\r?\n(.*?)\r?\n?endstream", re.S)


def public_email(email):
    domain = email.lower().rsplit(b"@", 1)[-1]
    return domain in {
        b"users.noreply.github.com",
        b"github.com",
        b"example.com",
        b"example.org",
    } or domain.endswith(b".invalid")


def identity_issues(name, email):
    issues = []
    if not public_email(email):
        issues.append("commit email must use a public no-reply identity")
    if not re.fullmatch(rb"[A-Za-z0-9_.\[\]-]+", name):
        issues.append("commit name must use a public account handle")
    return issues


def decoded_pdf_streams(data):
    for match in PDF_STREAM.finditer(data):
        header = data[max(0, match.start() - 1024) : match.start()]
        stream = match[1].strip()
        if b"/ASCII85Decode" in header:
            stream = base64.a85decode(stream, adobe=True)
        if b"/FlateDecode" in header:
            decoder = zlib.decompressobj()
            stream = decoder.decompress(stream, LIMIT)
            if decoder.unconsumed_tail:
                raise ValueError("PDF stream exceeds review limit")
        yield stream


def scan_content(filename, data):
    issues = set()
    if len(data) > LIMIT:
        return ["file exceeds bounded publication review limit"]
    image = filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    if image:
        return (
            ["image contains EXIF metadata"] if b"Exif\x00\x00" in data or b"eXIf" in data else []
        )
    parts = [data]
    if filename.lower().endswith(".pdf"):
        # Encoded binary payloads can coincidentally resemble email addresses.
        # Inspect document headers/metadata and decoded streams instead.
        parts = [PDF_STREAM.sub(b"", data)]
        try:
            parts.extend(decoded_pdf_streams(data))
        except (ValueError, zlib.error):
            issues.add("PDF stream could not be reviewed")
    elif b"\x00" in data:
        return []
    licensed = filename.startswith("data/public-machine-packs/")
    for part in parts:
        if HOME.search(part):
            issues.add("personal workstation home path")
        if SECRET.search(part):
            issues.add("credential pattern")
        if not licensed and any(not public_email(m[0]) for m in EMAIL.finditer(part)):
            issues.add("non-example email address")
    return sorted(issues)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def check(history=False):
    findings = []
    files = git("ls-files", "-z").decode().split("\0")[:-1]
    for filename in files:
        path = ROOT / filename
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            findings.append((filename, "tracked path escapes repository"))
            continue
        for issue in scan_content(filename, path.read_bytes()):
            findings.append((filename, issue))
    if history:
        objects = [
            line.split(b" ", 1) for line in git("rev-list", "--objects", "HEAD").splitlines()
        ]
        process = subprocess.Popen(
            ["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        try:
            for entry in objects:
                process.stdin.write(entry[0] + b"\n")
                process.stdin.flush()
                header = process.stdout.readline().split()
                body = process.stdout.read(int(header[2]))
                process.stdout.read(1)
                if header[1] == b"blob":
                    filename = entry[1].decode() if len(entry) > 1 else "historical blob"
                    findings.extend((filename, issue) for issue in scan_content(filename, body))
                elif header[1] == b"commit":
                    for name, email in re.findall(
                        rb"^(?:author|committer) (.*?) <([^>]+)>", body, re.M
                    ):
                        findings.extend(
                            ("commit " + entry[0].decode()[:12], issue)
                            for issue in identity_issues(name, email)
                        )
        finally:
            process.stdin.close()
            process.stdout.close()
            process.wait()
    return sorted(set(findings)), len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    findings, count = check(args.history)
    for filename, issue in findings:
        print(f"{filename}: {issue}")
    print(f"Reviewed {count} tracked files; {len(findings)} publication findings.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
