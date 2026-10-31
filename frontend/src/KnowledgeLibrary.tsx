import { useEffect, useState } from "react";
import { api } from "./api";
import { displayNotice } from "./locale";
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
            "Bibliotheksdetails sind nicht verfügbar. Vor der Quellenauswahl erneut versuchen.",
          );
      });
    return () => controller.abort();
  }, []);
  return (
    <details className="ux-library-options">
      <summary>
        Wissensbibliothek
        {documents.length ? ` · ${documents.length} Dokumente` : ""}
      </summary>
      <label className="ux-confirm">
        <input
          type="checkbox"
          checked={value.enabled}
          disabled={busy}
          onChange={(e) => onChange({ ...value, enabled: e.target.checked })}
        />
        <span>Dokumentbibliothek des Arbeitsbereichs durchsuchen</span>
      </label>
      <p className="ux-small">
        Antworten zitieren unterstützende Abschnitte. Einstiegshilfen sind
        generierte Beispiele; Produkthandbücher zeigen ihre Ausgabe und Lizenz.
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
  prefix = "",
}: {
  report: EvidenceReport;
  runId: string;
  prefix?: string;
}) {
  if (
    !report.library_snapshot?.length &&
    !report.library_retrieval?.method &&
    !report.machine_snapshot?.length &&
    !report.machine_retrieval?.method
  )
    return null;
  const references = report.library_citations || [];
  return (
    <section className="ux-siemens-references" aria-label="Bibliotheksquellen">
      <h2>
        {report.machine_id
          ? "Aus deinen ausgewählten Quellen"
          : "Aus deiner Wissensbibliothek"}
      </h2>
      {report.machine_retrieval?.notice && (
        <p className="ux-small">
          {displayNotice(report.machine_retrieval.notice)}
        </p>
      )}
      {report.library_retrieval?.notice && (
        <p className="ux-small">
          {displayNotice(report.library_retrieval.notice)}
        </p>
      )}
      {!references.length && (
        <p>
          {report.library_retrieval?.method || report.machine_retrieval?.method
            ? "Keine unterstützenden Abschnitte in den ausgewählten Dokumenten gefunden. Das beweist nicht, dass die Information fehlt."
            : "Bibliotheksquellen wurden ausgewählt, aber die Suche wurde nicht abgeschlossen. Diese Antwort benötigt eine Quellenprüfung."}
        </p>
      )}
      {references.map((r, i) => (
        <details
          key={r.citation_id}
          id={prefix + "source-" + r.citation_id}
          tabIndex={-1}
        >
          <summary>
            Bibliotheksquelle {i + 1}: {r.title} ·{" "}
            {r.line_start
              ? `lines ${r.line_start}–${r.line_end}`
              : r.pages?.length
                ? `pages ${r.pages.join(", ")}`
                : `page ${r.page}`}
          </summary>
          <p className="ux-small">
            {r.family} · {r.version} ·{" "}
            {r.data_policy === "synthetic"
              ? "Generiertes Demonstrationsmaterial"
              : r.data_policy === "internal"
                ? "Interne Referenz"
                : "Lizenzierte öffentliche Referenz"}
          </p>
          <blockquote>{r.text}</blockquote>
          <p className="ux-small">{r.license_note}</p>
          <a
            href={`/api/investigations/${encodeURIComponent(runId)}/library/documents/${encodeURIComponent(r.id)}/file`}
          >
            Quelldokument herunterladen
          </a>
        </details>
      ))}
      {!!(
        report.library_citation_checks?.unresolved.length ||
        report.library_citation_checks?.not_returned_by_tools.length
      ) && (
        <p className="ux-caution">
          Einige Bibliothekszitate konnten nicht aufgelöst werden oder stammen
          nicht aus der Suche. Prüfe die Abschnitte vor der Verwendung dieser
          Antwort.
        </p>
      )}
      <p className="ux-small">
        Dokumentausgabe und Produktgültigkeit prüfen. Zitate kennzeichnen
        Fundstellen; die Unterstützung der Aussagen muss weiterhin geprüft
        werden.
      </p>
    </section>
  );
}
