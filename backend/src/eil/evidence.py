"""Immutable, case-scoped evidence and deterministic lexical/CSV observations."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .analytics import ALLOWED_PERIODS, ALLOWED_STATIONS, EXPECTED_COLUMNS, station_metrics
from .database import MAX_CASES, StorageFull, configure, storage_error
from .pdf_ingest import MAX_PDF_BYTES, parse_pdf
from .runs import now

MAX_CSV_BYTES = 2 * 1024 * 1024


class EvidenceNotFound(LookupError):
    pass


class EvidenceConflict(RuntimeError):
    pass


def checked_id(value):
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError, TypeError) as exc:
        raise EvidenceNotFound("Evidence identifier not found") from exc
    return value


def inspection_rows(content):
    if not content or len(content) > MAX_CSV_BYTES:
        raise ValueError("CSV must contain 1 byte to 2 MiB")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        if (
            len(reader.fieldnames or []) != len(EXPECTED_COLUMNS)
            or set(reader.fieldnames) != EXPECTED_COLUMNS
        ):
            raise ValueError("CSV columns must exactly match the inspection schema")
        rows, ids = [], set()
        for raw in reader:
            if None in raw or any(v is None or len(v) > 128 for v in raw.values()):
                raise ValueError("CSV has missing, extra or oversized fields")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", raw["row_id"]) or raw["row_id"] in ids:
                raise ValueError("CSV row IDs must be unique safe identifiers")
            datetime.fromisoformat(raw["timestamp"])
            if raw["station_id"] not in ALLOWED_STATIONS or raw["period"] not in ALLOWED_PERIODS:
                raise ValueError("Invalid station or period")
            row = {k: raw[k] for k in ("row_id", "timestamp", "station_id", "period")}
            for key in EXPECTED_COLUMNS - row.keys():
                if not re.fullmatch(r"[0-9]{1,12}", raw[key]):
                    raise ValueError("CSV measurements must be non-negative bounded integers")
                row[key] = int(raw[key])
            if (
                row["inspected"] <= 0
                or row["false_ejects"] + row["true_rejects"] > row["inspected"]
            ):
                raise ValueError("Invalid inspection/rejection counts")
            row["csv_line"] = reader.line_num
            ids.add(row["row_id"])
            rows.append(row)
            if len(rows) > 20000:
                raise ValueError("CSV exceeds 20,000 rows")
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("CSV must be well-formed UTF-8") from exc
    if not rows:
        raise ValueError("CSV is empty")
    return rows


class EvidenceStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve() / "data"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "evidence.sqlite3"
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, title TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    filename TEXT, kind TEXT, sha256 TEXT, size INTEGER, created_at TEXT,
                    metadata TEXT, payload TEXT, raw BLOB, UNIQUE(case_id, sha256)
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, case_id TEXT, source_id TEXT REFERENCES sources(id),
                    page INTEGER, text TEXT, metadata TEXT
                );
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(cases)")}
            for name in ("owner_id", "deleted_at"):
                if name not in columns:
                    conn.execute(f"ALTER TABLE cases ADD COLUMN {name} TEXT")

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        configure(conn, "evidence")
        try:
            yield conn
            conn.commit()
        except BaseException as exc:
            conn.rollback()
            if storage_error(exc):
                raise StorageFull(
                    "Evidence storage quota reached. Review Trash and backups before adding data."
                ) from exc
            raise
        finally:
            conn.close()

    def create_case(self, title, *, owner_id=None):
        if not title.strip() or len(title) > 120:
            raise ValueError("Case title must contain 1-120 characters")
        from .auth import local_owner

        value = {
            "id": str(uuid.uuid4()),
            "title": title,
            "created_at": now(),
            "owner_id": owner_id or local_owner(self.directory.parent),
            "deleted_at": None,
        }
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT count(*) FROM cases").fetchone()[0] >= MAX_CASES:
                raise StorageFull(
                    "The installation case limit is reached; review retention before creating cases"
                )
            conn.execute(
                "INSERT INTO cases(id,title,created_at,owner_id,deleted_at) VALUES (?,?,?,?,?)",
                tuple(value.values()),
            )
        return value

    def case(self, case_id, *, include_deleted=False):
        checked_id(case_id)
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
            if row is None or (row["deleted_at"] is not None and not include_deleted):
                raise EvidenceNotFound("Case not found")
            return dict(row)

    def cases(self, *, limit=50, offset=0, owner_id=None, deleted=False):
        with self.connection() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM cases WHERE (? IS NULL OR owner_id=?) AND ((deleted_at IS NOT NULL)=?) ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                    (owner_id, owner_id, int(deleted), limit, offset),
                )
            ]

    @staticmethod
    def _metadata(row):
        value = {
            k: row[k] for k in ("id", "case_id", "filename", "kind", "sha256", "size", "created_at")
        }
        return {**value, **json.loads(row["metadata"])}

    def sources(self, case_id, allowed=None):
        self.case(case_id)
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sources WHERE case_id=? ORDER BY created_at,id", (case_id,)
            )
            return [self._metadata(row) for row in rows if allowed is None or row["id"] in allowed]

    def source(self, case_id, source_id, allowed=None):
        checked_id(case_id)
        checked_id(source_id)
        if allowed is not None and source_id not in allowed:
            raise EvidenceNotFound("Source is outside this investigation's evidence snapshot")
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE case_id=? AND id=?", (case_id, source_id)
            ).fetchone()
            if row is None:
                raise EvidenceNotFound("Source not found in this case")
            return row

    def ingest(self, case_id, filename, content, *, pdf_parser=parse_pdf, data_policy="synthetic"):
        self.case(case_id)
        if data_policy not in {"synthetic", "licensed-public"}:
            raise ValueError("Only synthetic or explicitly licensed public demo data are allowed")
        if (
            not filename
            or len(filename) > 160
            or any(ord(c) < 32 for c in filename)
            or any(c in filename for c in "/\\:")
        ):
            raise ValueError("Upload a plain PDF/CSV filename without a path")
        suffix = Path(filename).suffix.lower()
        if suffix not in {".pdf", ".csv"}:
            raise ValueError("Only PDF and inspection CSV files are accepted")
        if not content or len(content) > (MAX_PDF_BYTES if suffix == ".pdf" else MAX_CSV_BYTES):
            raise ValueError("Upload exceeds the PDF 10 MiB / CSV 2 MiB limit or is empty")
        digest = hashlib.sha256(content).hexdigest()
        current = self.sources(case_id)
        if any(s["sha256"] == digest for s in current):
            raise EvidenceConflict("This file is already present in the case")
        if len(current) >= 10 or sum(s["size"] for s in current) + len(content) > 30 * 1024 * 1024:
            raise EvidenceConflict("Case limit: ten sources and 30 MiB total uploads")
        if suffix == ".csv":
            payload = inspection_rows(content)
            meta = {"row_count": len(payload), "parser": "inspection-csv-v1"}
            chunks = []
        else:
            if not content.startswith(b"%PDF-"):
                raise ValueError("Invalid PDF signature")
            parsed = pdf_parser(content)
            chunks = parsed["chunks"]
            payload = None
            meta = {k: v for k, v in parsed.items() if k != "chunks"}
        meta["data_policy"] = data_policy
        source_id = str(uuid.uuid4())
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current_case = conn.execute(
                "SELECT deleted_at FROM cases WHERE id=?", (case_id,)
            ).fetchone()
            if not current_case or current_case[0] is not None:
                raise EvidenceNotFound("Case not found")
            count, size = conn.execute(
                "SELECT count(*), coalesce(sum(size),0) FROM sources WHERE case_id=?", (case_id,)
            ).fetchone()
            if count >= 10 or size + len(content) > 30 * 1024 * 1024:
                raise EvidenceConflict("Case limit: ten sources and 30 MiB total uploads")
            try:
                conn.execute(
                    "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        source_id,
                        case_id,
                        filename,
                        suffix[1:],
                        digest,
                        len(content),
                        now(),
                        json.dumps(meta),
                        json.dumps(payload),
                        content,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise EvidenceConflict("This file is already present in the case") from exc
            for index, chunk in enumerate(chunks):
                cid = f"pdf:{source_id}:p{chunk['page']}:c{index}"
                conn.execute(
                    "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                    (cid, case_id, source_id, chunk["page"], chunk["text"], json.dumps(chunk)),
                )
        return self._metadata(self.source(case_id, source_id))

    def snapshot(self, case_id):
        sources = self.sources(case_id)
        if not sources:
            raise EvidenceConflict("Upload evidence before starting this case's investigation")
        return [s["id"] for s in sources]

    def search(self, case_id, query, *, limit=3, allowed=None):
        if not query.strip() or len(query) > 500 or not 1 <= limit <= 5:
            raise ValueError("Search requires 1-500 characters and a limit of 1-5")
        sources = self.sources(case_id, allowed)
        ids = [s["id"] for s in sources if s["kind"] == "pdf"]
        terms = sorted(set(re.findall(r"\w+", query.lower(), flags=re.UNICODE)))[:32]
        hits = []
        if ids and terms:
            # Literal words only. Never accept FTS syntax or model-authored SQL.
            expression = " OR ".join('"' + term + '"' for term in terms)
            placeholders = ",".join("?" for _ in ids)
            with self.connection() as conn:
                corpus = conn.execute(
                    f"SELECT id,text FROM chunks WHERE case_id=? AND source_id IN ({placeholders}) ORDER BY id",
                    (case_id, *ids),
                ).fetchall()
            # Build the bounded index from this immutable snapshot only. Other cases
            # and later uploads cannot influence its BM25 corpus statistics/ranking.
            index = sqlite3.connect(":memory:")
            try:
                index.execute("CREATE VIRTUAL TABLE lexical USING fts5(text, chunk_id UNINDEXED)")
                index.executemany(
                    "INSERT INTO lexical VALUES (?,?)", [(r["text"], r["id"]) for r in corpus]
                )
                for cid, score in index.execute(
                    "SELECT chunk_id,bm25(lexical) FROM lexical WHERE lexical MATCH ? ORDER BY bm25(lexical),chunk_id LIMIT ?",
                    (expression, limit),
                ):
                    hit = self.resolve(case_id, cid, allowed)
                    hit["lexical_score"] = -score
                    # Include the adjacent extracted items on the same page.
                    # A conclusion is often split from its matching paragraph.
                    index_number = int(cid.rsplit(":c", 1)[1])
                    neighbors = []
                    for neighbor in (index_number - 1, index_number + 1):
                        if neighbor < 0:
                            continue
                        ref = cid.rsplit(":c", 1)[0] + f":c{neighbor}"
                        try:
                            neighbors.append(self.resolve(case_id, ref, allowed))
                        except EvidenceNotFound:
                            pass
                    hit["context"] = neighbors
                    hits.append(hit)
            finally:
                index.close()
        return {
            "query": query,
            "method": "sqlite-fts5-bm25-snapshot-literal-v1",
            "terms": terms,
            "limit": limit,
            "source_ids": ids,
            "hits": hits,
            "uncertainty": "Lexical relevance is not factual confidence; an empty result is not proof of absence.",
        }

    def resolve(self, case_id, citation_id, allowed=None):
        parts = citation_id.split(":")
        if len(parts) not in {3, 4} or parts[0] not in {"pdf", "csv"}:
            raise EvidenceNotFound("Citation not found")
        row = self.source(case_id, parts[1], allowed)
        result = {"citation_id": citation_id, "source_id": row["id"], **self._metadata(row)}
        if (
            len(parts) == 3
            and parts[0] == "csv"
            and row["kind"] == "csv"
            and re.fullmatch(r"r[0-9]{1,5}", parts[2])
        ):
            records = json.loads(row["payload"])
            index = int(parts[2][1:])
            if index >= len(records):
                raise EvidenceNotFound("CSV row not found")
            return {**result, "row": records[index]}
        with self.connection() as conn:
            chunk = conn.execute(
                "SELECT metadata FROM chunks WHERE case_id=? AND source_id=? AND id=?",
                (case_id, parts[1], citation_id),
            ).fetchone()
        if chunk is None:
            raise EvidenceNotFound("PDF chunk not found")
        return {**result, **json.loads(chunk[0])}

    def compare(self, case_id, source_id, allowed=None):
        source = self.source(case_id, source_id, allowed)
        if source["kind"] != "csv":
            raise ValueError("Select an inspection CSV source")
        rows = json.loads(source["payload"])
        ranking, incomplete = [], []
        for station in sorted({r["station_id"] for r in rows}):
            periods = {r["period"] for r in rows if r["station_id"] == station}
            if periods != ALLOWED_PERIODS:
                incomplete.append(station)
                continue
            before, after = (station_metrics(station, p, rows) for p in ("baseline", "incident"))
            examples = [
                f"csv:{source_id}:r{i}"
                for period in ("baseline", "incident")
                for i in [
                    next(
                        j
                        for j, r in enumerate(rows)
                        if r["station_id"] == station and r["period"] == period
                    )
                ]
            ]
            ranking.append(
                {
                    "station_id": station,
                    "baseline_rate": before["false_eject_rate"],
                    "incident_rate": after["false_eject_rate"],
                    "delta_percentage_points": round(
                        100 * (after["false_eject_rate"] - before["false_eject_rate"]), 4
                    ),
                    "baseline_inspected": before["inspected"],
                    "incident_inspected": after["inspected"],
                    "supporting_row_count": len(before["source_rows"]) + len(after["source_rows"]),
                    "example_citations": examples,
                }
            )
        if not ranking:
            raise ValueError("No station has both baseline and incident observations")
        ranking.sort(key=lambda r: (-r["delta_percentage_points"], r["station_id"]))
        return {
            "source": self._metadata(source),
            "ranking": ranking,
            "incomplete_stations": incomplete,
            "query_provenance": {
                "operation": "station_period_comparison",
                "metric": "sum(false_ejects)/sum(inspected)",
                "source_id": source_id,
                "sha256": source["sha256"],
                "rows_scanned": len(rows),
                "rows_used": sum(r["supporting_row_count"] for r in ranking),
                "excluded_rows": sum(1 for r in rows if r["station_id"] in incomplete),
                "group_by": ["station_id", "period"],
                "rate_rounding_digits": 6,
                "delta_rounding_digits": 4,
            },
            "uncertainty": "Descriptive comparison only. Example citations are not the complete aggregation. Correlation does not establish causation; no statistical or causal confidence is estimated.",
        }
