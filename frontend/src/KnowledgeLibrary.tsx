import { useEffect, useState } from "react";
import { api } from "./api";
import type { EvidenceReport } from "./types";

export type LibraryDocument = {
  id: string;
  title: string;
  filename: string;
  family: string;
  version: string;
  data_policy: string;
  license_note: string;
  active: boolean;
  indexed_passages: number;
  passages: number;
};
export type LibrarySelection = { enabled: boolean; documentIds?: string[] };

export function LibraryChooser({
  value,
  onChange,
  busy,
}: {
  value: LibrarySelection;
  onChange: (next: LibrarySelection) => void;
  busy: boolean;
}) {
  const [documents, setDocuments] = useState<LibraryDocument[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    void api<{ documents: LibraryDocument[] }>("/api/library/documents", {
      signal: controller.signal,
    })
      .then((r) => setDocuments((r.documents || []).filter((d) => d.active)))
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            "Library details are unavailable. Retry before selecting sources.",
          );
      });
    return () => controller.abort();
  }, []);
  return (
    <details className="ux-library-options">
      <summary>
        Knowledge library
        {documents.length ? ` · ${documents.length} documents` : ""}
      </summary>
      <label className="ux-confirm">
        <input
          type="checkbox"
          checked={value.enabled}
          disabled={busy}
          onChange={(e) => onChange({ ...value, enabled: e.target.checked })}
        />
        <span>Search the workspace document library</span>
      </label>
      <p className="ux-small">
        Answers cite supporting passages. Starter guides are generated examples;
        product manuals show their own edition and licence.
      </p>
      {error && <p role="status">{error}</p>}
      {value.enabled &&
        documents.map((d) => (
          <label className="ux-confirm" key={d.id}>
            <input
              type="checkbox"
              disabled={busy}
              checked={
                value.documentIds === undefined ||
                value.documentIds.includes(d.id)
              }
              onChange={(e) => {
                const selected =
                  value.documentIds || documents.map((x) => x.id);
                onChange({
                  enabled: true,
                  documentIds: e.target.checked
                    ? [...selected, d.id]
                    : selected.filter((id) => id !== d.id),
                });
              }}
            />
            <span>
              {d.title}
              <small>
                {d.family} · {d.version}
              </small>
            </span>
          </label>
        ))}
    </details>
  );
}

export function LibraryReferences({
  report,
  runId,
}: {
  report: EvidenceReport;
  runId: string;
}) {
  if (!report.library_snapshot?.length && !report.library_retrieval?.method)
    return null;
  const references = report.library_citations || [];
  return (
    <section className="ux-siemens-references" aria-label="Library sources">
      <h2>From your knowledge library</h2>
      {report.library_retrieval?.notice && (
        <p className="ux-small">{report.library_retrieval.notice}</p>
      )}
      {!references.length && (
        <p>
          {report.library_retrieval?.method
            ? "No supporting passages were found in the selected documents. This does not prove the information is absent."
            : "Library sources were selected, but retrieval was not completed. This answer needs a source check."}
        </p>
      )}
      {references.map((r, i) => (
        <details key={r.citation_id} id={"source-" + r.citation_id}>
          <summary>
            Library source {i + 1}: {r.title} ·{" "}
            {r.line_start
              ? `lines ${r.line_start}–${r.line_end}`
              : r.pages?.length
                ? `pages ${r.pages.join(", ")}`
                : `page ${r.page}`}
          </summary>
          <p className="ux-small">
            {r.family} · {r.version} ·{" "}
            {r.data_policy === "synthetic"
              ? "Generated demonstration material"
              : "Licensed public reference"}
          </p>
          <blockquote>{r.text}</blockquote>
          <p className="ux-small">{r.license_note}</p>
          <a
            href={`/api/investigations/${encodeURIComponent(runId)}/library/documents/${encodeURIComponent(r.id)}/file`}
          >
            Download source document
          </a>
        </details>
      ))}
      {!!(
        report.library_citation_checks?.unresolved.length ||
        report.library_citation_checks?.not_returned_by_tools.length
      ) && (
        <p className="ux-caution">
          Some library citations were unresolved or were not returned by
          retrieval. Review the source passages before relying on this answer.
        </p>
      )}
      <p className="ux-small">
        Check the document edition and product applicability. Citations identify
        passages; claim support still needs review.
      </p>
    </section>
  );
}
