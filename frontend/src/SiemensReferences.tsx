import { useLanguage, t } from "./i18n";
import type { EvidenceReport } from "./types";
import { siemensUrl } from "./siemens";
import { displayNotice } from "./locale";

export default function SiemensReferences({
  report,
}: {
  report: EvidenceReport;
}) {
  useLanguage();
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
        {t("Siemens-Quelle")} {references.indexOf(r) + 1}: {r.title}
      </a>
      <small>
        {r.kind === "curated_manual"
          ? t("Geprüfter Handbuchkandidat")
          : t("Öffentliche Referenz")}
        {r.tia_version ? ` · ${r.tia_version}` : ""}
        {r.edition ? ` · ${r.edition}` : ""}
      </small>
    </li>
  );
  return (
    <section
      className="ux-siemens-references"
      aria-label={t("Siemens-Dokumentation")}
    >
      <h2>{t("Siemens-Dokumentation")}</h2>
      {lookup.query_origin === "canonical-human-diagnostic" && (
        <p>
          {t(
            "Automatische Suche: nur die erkannte SPS-Produktfamilie und die in dieser Frage eingegebenen Diagnosekennungen.",
          )}
        </p>
      )}
      <p>
        {lookup.remote_search_status === "unavailable"
          ? t(
              "Die Siemens-Livesuche war nicht verfügbar. Dies sind geprüfte Handbuchkandidaten aus dem lokalen Index.",
            )
          : lookup.connection_verified
            ? t("Öffentliche Siemens-Dokumentation zu dieser Frage durchsucht.")
            : t("Keine abgeschlossene Siemens-Suche verfügbar.")}
      </p>
      <p className="ux-small">
        {(lookup.version_notice && displayNotice(lookup.version_notice)) ||
          t(
            "Vor der Anwendung genaue CPU, Firmware und TIA-Portal-Version prüfen.",
          )}
      </p>
      {lookup.error && (
        <p className="ux-small">{displayNotice(lookup.error)}</p>
      )}
      <ul>{visible.map(referenceItem)}</ul>
      {!!remaining.length && (
        <details>
          <summary>
            {t("Weitere Siemens-Referenzen (")}
            {remaining.length})
          </summary>
          <ul>{remaining.map(referenceItem)}</ul>
        </details>
      )}
      {!references.length && (
        <p>
          {t(
            "Keine Quellenlinks zurückgegeben. Die technischen Aussagen der Antwort konnten nicht anhand der Siemens-Dokumentation geprüft werden.",
          )}
        </p>
      )}
      {!!report.external_reference_checks?.unresolved.length && (
        <p className="ux-caution">
          {t(
            "Einige Quellenangaben der Antwort konnten dieser Suche nicht zugeordnet werden. Prüfe die obigen Links.",
          )}
        </p>
      )}
      <details>
        <summary>{t("Was an Siemens gesendet wurde")}</summary>
        <p>
          {t(
            "Nur diese öffentliche Suchanfrage wurde gesendet. Dateien, Fallverlauf und Modellausgaben blieben ausgeschlossen.",
          )}
        </p>
        <pre>{lookup.outbound_query}</pre>
      </details>
    </section>
  );
}
