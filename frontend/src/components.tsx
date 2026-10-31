import { useEffect, useId, useRef, type ReactNode } from "react";
import {
  X,
  FileText,
  Table2,
  ArrowUpRight,
  Check,
  Circle,
  Wrench,
  Cpu,
} from "lucide-react";
import type { Citation, Comparison, RunEvent } from "./types";
import { statusLabel } from "./locale";

export const fmt = (n: number) => new Intl.NumberFormat("de-DE").format(n);
export const time = (s: string) =>
  new Date(s).toLocaleTimeString("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
export function Status({ value }: { value: string }) {
  return (
    <span className={`status ${value}`}>
      <i />
      {statusLabel(value)}
    </span>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <FileText size={22} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null),
    id = useId();
  useEffect(() => {
    ref.current?.showModal();
    const el = ref.current;
    return () => el?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={wide ? "modal wide" : "modal"}
      aria-labelledby={id}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="modal-head">
        <h2 id={id}>{title}</h2>
        <button
          className="icon-button"
          aria-label="Dialog schließen"
          onClick={onClose}
        >
          <X size={19} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Json({ value }: { value: unknown }) {
  let parsed = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      /* Render text verbatim. */
    }
  }
  return (
    <pre className="json">
      {typeof parsed === "string" ? parsed : JSON.stringify(parsed, null, 2)}
    </pre>
  );
}
export function CitationView({ citation }: { citation: Citation }) {
  return (
    <div className="citation-view">
      <div className="source-heading">
        {citation.citation_id.startsWith("pdf:") ? (
          <FileText size={22} />
        ) : (
          <Table2 size={22} />
        )}
        <div>
          <strong>{citation.filename}</strong>
          <p>
            {citation.citation_id.startsWith("pdf:")
              ? `Seite ${(citation.pages || [citation.page]).join(", ")}`
              : `CSV-Zeile ${citation.row?.csv_line} · ${citation.row?.row_id || ""}`}
          </p>
        </div>
      </div>
      {citation.text && <blockquote>{citation.text}</blockquote>}
      {citation.row && <Json value={citation.row} />}
      <label>Citation ID</label>
      <code className="break">{citation.citation_id}</code>
      <label>SHA-256 der Quelle</label>
      <code className="break">{citation.sha256}</code>
      <p className="muted small">
        Die Referenz bestätigt eine Fundstelle. Sie belegt nicht die Richtigkeit
        einer Aussage.
      </p>
    </div>
  );
}
export function StationChart({
  data,
  onCitation,
}: {
  data: Comparison;
  onCitation: (id: string) => void;
}) {
  const ranking = [...data.ranking].sort((a, b) =>
    a.station_id.localeCompare(b.station_id),
  );
  const max =
    Math.max(
      0.01,
      ...ranking.flatMap((x) => [x.baseline_rate, x.incident_rate]),
    ) * 1.2;
  const width = 660,
    height = 232,
    bottom = 193,
    top = 24,
    left = 52,
    plotWidth = 570;
  return (
    <>
      <div className="chart-legend">
        <span>
          <i className="baseline-key" />
          Ausgangszeitraum
        </span>
        <span>
          <i className="incident-key" />
          Störungszeitraum
        </span>
        <span className="muted">Fehlausschussquote (%)</span>
      </div>
      <svg
        className="station-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Fehlausschussquoten nach Station und Zeitraum; genaue Werte in der folgenden Tabelle"
      >
        {[0, 1, 2, 3].map((i) => {
          const y = bottom - ((bottom - top) * i) / 3;
          return (
            <g key={i}>
              <line
                x1={left}
                x2={left + plotWidth}
                y1={y}
                y2={y}
                className="grid-line"
              />
              <text
                x={left - 10}
                y={y + 4}
                textAnchor="end"
                className="chart-label"
              >
                {((max * 100 * i) / 3).toFixed(0)}%
              </text>
            </g>
          );
        })}
        {ranking.map((row, index) => {
          const center = left + (plotWidth * (index + 0.5)) / ranking.length;
          return (
            <g key={row.station_id}>
              <rect
                x={center - 27}
                y={bottom - (row.baseline_rate / max) * (bottom - top)}
                width="23"
                height={(row.baseline_rate / max) * (bottom - top)}
                rx="4"
                className="bar-baseline"
              />
              <rect
                x={center + 2}
                y={bottom - (row.incident_rate / max) * (bottom - top)}
                width="23"
                height={(row.incident_rate / max) * (bottom - top)}
                rx="4"
                className="bar-incident"
              />
              <text
                x={center}
                y={bottom + 25}
                textAnchor="middle"
                className="chart-label station"
              >
                {row.station_id}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Station</th>
              <th>Ausgangszeitraum</th>
              <th>Störungszeitraum</th>
              <th>Änderung</th>
              <th>Belege</th>
            </tr>
          </thead>
          <tbody>
            {data.ranking.map((r, i) => (
              <tr key={r.station_id}>
                <td>
                  <span className="station-id">{r.station_id}</span>
                  {i === 0 && (
                    <span className="subtle-tag">Größte Abweichung</span>
                  )}
                </td>
                <td>{(100 * r.baseline_rate).toFixed(2)}%</td>
                <td>{(100 * r.incident_rate).toFixed(2)}%</td>
                <td className={r.delta_percentage_points > 1 ? "delta" : ""}>
                  {r.delta_percentage_points > 0 ? "+" : ""}
                  {r.delta_percentage_points.toFixed(2)} pp
                </td>
                <td>
                  <button
                    className="text-button"
                    onClick={() => onCitation(r.example_citations[0])}
                  >
                    Zeile anzeigen <ArrowUpRight size={13} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="method">
        <summary>Berechnung und Herkunft der Quellen</summary>
        <Json value={data.query_provenance} />
        <p className="small muted">{data.uncertainty}</p>
      </details>
    </>
  );
}
export function Timeline({
  events,
  selected,
  onSelect,
}: {
  events: RunEvent[];
  selected: number | null;
  onSelect: (event: RunEvent) => void;
}) {
  const visible = events.filter((e) => e.type !== "checkpoint");
  return (
    <div className="timeline">
      {visible.map((e) => {
        const isTool = e.type.startsWith("tool_"),
          Icon = isTool
            ? Wrench
            : e.type.startsWith("model_")
              ? Cpu
              : e.type === "completed"
                ? Check
                : Circle;
        return (
          <button
            className={`event ${selected === e.id ? "selected" : ""}`}
            key={e.id}
            onClick={() => onSelect(e)}
          >
            <span className={`event-icon ${isTool ? "tool" : ""}`}>
              <Icon size={15} />
            </span>
            <span className="event-copy">
              <strong>{e.type.replaceAll("_", " ")}</strong>
              <span>
                {String(
                  e.data.name ||
                    (typeof e.data.error === "object" && e.data.error
                      ? (e.data.error as { message?: string }).message
                      : e.data.error) ||
                    (e.data.tokens
                      ? `${e.data.tokens} tokens`
                      : `Ereignis ${e.id}`),
                )}
              </span>
            </span>
            <time>{time(e.at)}</time>
          </button>
        );
      })}
      {!visible.length && (
        <Empty title="Wartet auf Ereignisse">
          Aktivitäten der Untersuchung erscheinen hier fortlaufend.
        </Empty>
      )}
    </div>
  );
}
