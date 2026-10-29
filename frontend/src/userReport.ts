import type { Comparison, EvidenceReport, Run } from "./types";
import { siemensUrl } from "./siemens";

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
  const publicReferences = (report.external_references || []).filter((r) =>
    siemensUrl(r.url),
  );
  const externalSection = report.integrations?.siemens?.enabled
    ? `<h2>Siemens documentation</h2><p>${text(report.integrations.siemens.version_notice || "Public references; exact CPU/firmware applicability is unverified.")}</p><ul>${publicReferences.map((r, i) => `<li><a href="${text(r.url)}" target="_blank" rel="noopener noreferrer">Siemens source ${i + 1}: ${text(r.title)}</a><br><small>${text(r.citation_id)}</small></li>`).join("")}</ul><details><summary>Public query sent to Siemens</summary><pre>${text(report.integrations.siemens.outbound_query)}</pre></details>`
    : "";
  const rows =
    comparison?.ranking
      .map(
        (r) =>
          `<tr><td>${text(r.station_id)}</td><td>${(r.baseline_rate * 100).toFixed(2)}%</td><td>${(r.incident_rate * 100).toFixed(2)}%</td><td>${r.delta_percentage_points.toFixed(4)} pp</td></tr>`,
      )
      .join("") || "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Investigation report</title><style>body{font:16px/1.7 system-ui,sans-serif;color:#242331;max-width:900px;margin:50px auto;padding:0 24px}h1{line-height:1.3}p,pre{white-space:pre-wrap;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}.note{padding:14px;background:#f6f3fb;border-radius:6px}small{color:#666}pre{font:12px/1.6 monospace}@media print{body{margin:0}details{display:block}}</style></head><body>
<small>Engineering Intelligence Lab · Synthetic / licensed public evidence</small><h1>${text(run.question)}</h1><p>Status: ${text(run.status)}</p>
${rows ? `<h2>Inspection comparison</h2><p>Source: ${text(filename)}. Rate = total false ejects / total inspected, grouped by station and period.</p><table><thead><tr><th>Station</th><th>Before</th><th>During incident</th><th>Change</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
<h2>Investigation notes</h2><p>${text(report.answer || "No final answer was produced.")}</p><p class="note">These findings require review. Correlation does not establish causation; statistical confidence and claim entailment have not been verified.</p>
<h2>Sources</h2>${report.citations.map((c, i) => `<h3>Source ${i + 1}: ${text(c.filename)}</h3><p>${text(c.text || JSON.stringify(c.row))}</p><small>${text(c.citation_id)} · SHA-256 ${text(c.sha256)}</small>`).join("") || "<p>No source references were returned.</p>"}
${externalSection}<h2>Limitations</h2><ul>${report.uncertainty.limitations.map((x) => `<li>${text(x)}</li>`).join("")}</ul><details><summary>Full evidence and calculation record</summary><pre>${text(JSON.stringify(report, null, 2))}</pre></details><p><small>Run ${text(run.id)}. Downloaded report; this does not save or approve a draft in the application.</small></p></body></html>`;
}
