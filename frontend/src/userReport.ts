import { tr, t } from "./i18n";
import type { Comparison, EvidenceReport, Run } from "./types";
import { siemensUrl } from "./siemens";
import { displayNotice } from "./locale";

export function escapeHtml(value: unknown): string {
  return String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
}
export function userReport(
  run: Run,
  report: EvidenceReport,
  comparison: Comparison | null,
  filename: string,
) {
  const text = escapeHtml;
  const librarySection = report.library_citations?.length
    ? tr`<h2>Abschnitte der Wissensbibliothek</h2>${report.library_citations.map((r, i) => tr`<h3>Bibliotheksquelle ${i + 1}: ${text(r.title)} · ${r.line_start ? `lines ${r.line_start}-${r.line_end}` : `pages ${(r.pages || [r.page]).join(", ")}`}</h3><p>${text(r.family)} · ${text(r.version)}</p><blockquote>${text(r.text)}</blockquote><small>${text(r.citation_id)} · ${text(r.license_note)}</small>`).join("")}`
    : "";
  const publicReferences = (report.external_references || []).filter((r) =>
    siemensUrl(r.url),
  );
  const externalSection = report.integrations?.siemens?.enabled
    ? tr`<h2>Siemens-Dokumentation</h2><p>${text(report.integrations.siemens.version_notice || t("Öffentliche Referenzen; Gültigkeit für genaue CPU/Firmware ist nicht geprüft."))}</p><ul>${publicReferences.map((r, i) => tr`<li><a href="${text(r.url)}" target="_blank" rel="noopener noreferrer">Siemens-Quelle ${i + 1}: ${text(r.title)}</a><br><small>${text(r.citation_id)}</small></li>`).join("")}</ul><details><summary>Öffentliche Suchanfrage an Siemens</summary><pre>${text(report.integrations.siemens.outbound_query)}</pre></details>`
    : "";
  const rows =
    comparison?.ranking
      .map(
        (r) =>
          `<tr><td>${text(r.station_id)}</td><td>${(r.baseline_rate * 100).toFixed(2)}%</td><td>${(r.incident_rate * 100).toFixed(2)}%</td><td>${r.delta_percentage_points.toFixed(4)} pp</td></tr>`,
      )
      .join("") || "";
  return tr`<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Untersuchungsbericht</title><style>body{font:16px/1.7 system-ui,sans-serif;color:#242331;max-width:900px;margin:50px auto;padding:0 24px}h1{line-height:1.3}p,pre{white-space:pre-wrap;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}.note{padding:14px;background:#f6f3fb;border-radius:6px}small{color:#666}pre{font:12px/1.6 monospace}@media print{body{margin:0}details{display:block}}</style></head><body>
<small>Engineering Intelligence Lab · ${report.machine_id ? t("Private Maschinenuntersuchung") : t("Synthetische / lizenzierte öffentliche Belege")}</small><h1>${text(run.question)}</h1><p>Status: ${text(run.status)}</p>
${rows ? tr`<h2>Prüfvergleich</h2><p>Quelle: ${text(filename)}. Quote = gesamte Fehlausschüsse / gesamte Prüfungen, gruppiert nach Station und Zeitraum.</p><table><thead><tr><th>Station</th><th>Vorher</th><th>Im Störungszeitraum</th><th>Änderung</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
<h2>Untersuchungsnotizen</h2><p>${text(report.answer || t("Keine abschließende Antwort erstellt."))}</p><p class="note">Diese Befunde müssen geprüft werden. Korrelation belegt keine Ursache; statistische Sicherheit und die Unterstützung der Aussagen wurden nicht verifiziert.</p>
<h2>Quellen</h2>
${report.citations.map((c, i) => tr`<h3>Quelle ${i + 1}: ${text(c.filename)}</h3><p>${text(c.text || JSON.stringify(c.row))}</p><small>${text(c.citation_id)} · SHA-256 ${text(c.sha256)}</small>`).join("") || t("<p>Keine Quellenverweise zurückgegeben.</p>")}
${externalSection}${librarySection}<h2>Einschränkungen</h2><ul>${report.uncertainty.limitations.map((x) => `<li>${text(displayNotice(x))}</li>`).join("")}</ul><details><summary>Vollständige Beleg- und Berechnungsübersicht</summary><pre>${text(JSON.stringify(report, null, 2))}</pre></details><p><small>Untersuchung ${text(run.id)}. Heruntergeladener Bericht; dies speichert oder genehmigt keinen Entwurf in der Anwendung.</small></p></body></html>`;
}
