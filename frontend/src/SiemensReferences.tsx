import type { EvidenceReport } from "./types";
import { siemensUrl } from "./siemens";

export default function SiemensReferences({
  report,
}: {
  report: EvidenceReport;
}) {
  const lookup = report.integrations?.siemens;
  if (!lookup?.enabled) return null;
  const references = (report.external_references || []).filter((r) =>
    siemensUrl(r.url),
  );
  const preferred = references.filter(
    (r) => r.cited_in_answer || r.kind === "curated_manual",
  );
  const visible = preferred.length ? preferred : references.slice(0, 2);
  const remaining = references.filter((r) => !visible.includes(r));
  const referenceItem = (r: (typeof references)[number]) => (
    <li key={r.citation_id}>
      <a href={r.url} target="_blank" rel="noopener noreferrer">
        Siemens source {references.indexOf(r) + 1}: {r.title}
      </a>
      <small>
        {r.kind === "curated_manual"
          ? "Reviewed manual candidate"
          : "Public reference"}
        {r.tia_version ? ` · ${r.tia_version}` : ""}
        {r.edition ? ` · ${r.edition}` : ""}
      </small>
    </li>
  );
  return (
    <section
      className="ux-siemens-references"
      aria-label="Siemens documentation"
    >
      <h2>Siemens documentation</h2>
      <p>
        {lookup.remote_search_status === "unavailable"
          ? "Live Siemens search was unavailable. These are reviewed manual candidates from the local index."
          : lookup.connection_verified
            ? "Checked Siemens public documentation for this question."
            : "No completed Siemens lookup is available."}
      </p>
      <p className="ux-small">
        {lookup.version_notice ||
          "Check the exact CPU, firmware and TIA Portal version before applying guidance."}
      </p>
      {lookup.error && <p className="ux-small">{lookup.error}</p>}
      <ul>{visible.map(referenceItem)}</ul>
      {!!remaining.length && (
        <details>
          <summary>Other Siemens references ({remaining.length})</summary>
          <ul>{remaining.map(referenceItem)}</ul>
        </details>
      )}
      {!references.length && (
        <p>
          No source links were returned. The answer's technical claims could not
          be verified against Siemens documentation.
        </p>
      )}
      {!!report.external_reference_checks?.unresolved.length && (
        <p className="ux-caution">
          Some answer references could not be matched to this lookup. Review the
          links above.
        </p>
      )}
      <details>
        <summary>What was sent to Siemens</summary>
        <p>
          Only this public query was sent. Files, case history and model output
          were excluded.
        </p>
        <pre>{lookup.outbound_query}</pre>
      </details>
    </section>
  );
}
