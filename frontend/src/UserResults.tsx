import { t, useLanguage, tr } from "./i18n";
import { useEffect, useState } from "react";
import { displayNotice } from "./locale";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  FileText,
  LoaderCircle,
  Pause,
  Play,
  Table2,
} from "lucide-react";
import { api, download, post } from "./api";
import { Modal } from "./components";
import { stopped, useInvestigation } from "./useInvestigation";
import { friendlyStatus, readableAnswer } from "./userFlow";
import { userReport } from "./userReport";
import { continuationLabel, tokenContinuation } from "./budgetRecovery";
import SafeAnswer from "./SafeAnswer";
import SiemensReferences from "./SiemensReferences";
import { LibraryReferences } from "./KnowledgeLibrary";
import { advancedUrl, message } from "./UserApp";
import type {
  CaseDetail,
  Citation,
  Comparison,
  EvidenceReport,
  RunEvent,
} from "./types";

function progressText(status: string, events: RunEvent[]) {
  if (status !== "running") return friendlyStatus(status);
  const last = events.at(-1);
  const name = String(last?.data.name || "");
  if (name.includes("knowledge_library"))
    return t("Wissensbibliothek wird durchsucht…");
  if (last?.type === "siemens_lookup_started")
    return t("Siemens-Dokumentation wird geprüft…");
  if (name.includes("siemens")) return t("Siemens-Dokumentation wird geprüft…");
  if (name.includes("search") || name.includes("citation"))
    return t("Belege werden gelesen…");
  if (name.includes("compare")) return t("Prüfdaten werden untersucht…");
  return t("Frage und Quellen werden geprüft…");
}
export default function UserResults({
  id,
  caseId,
  detail,
  onBack,
  onAnother,
}: {
  id: string;
  caseId: string;
  detail: CaseDetail | null;
  onBack: () => void;
  onAnother: () => void;
}) {
  useLanguage();
  const [revision, setRevision] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const {
    run: loadedRun,
    events,
    error: connectionError,
  } = useInvestigation(id, revision);
  const run =
    loadedRun && (loadedRun.case_id || "") === caseId ? loadedRun : null;
  const [report, setReport] = useState<EvidenceReport | null>(null),
    [sourceId, setSourceId] = useState("");
  const [comparison, setComparison] = useState<Comparison | null>(null),
    [compareError, setCompareError] = useState("");
  const [citation, setCitation] = useState<Citation | null>(null);
  useEffect(() => {
    setReport(null);
    setError("");
    if (!run || !stopped.has(run.status)) return;
    const c = new AbortController();
    void api<EvidenceReport>(`/api/investigations/${id}/export`, {
      signal: c.signal,
    })
      .then((r) => {
        setReport(r);
        setSourceId((previous) =>
          r.source_snapshot.some((s) => s.id === previous)
            ? previous
            : r.source_snapshot.find((s) => s.kind === "csv")?.id || "",
        );
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(message(e));
      });
    return () => c.abort();
  }, [id, run?.status, revision]);
  useEffect(() => {
    setComparison(null);
    setCompareError("");
    if (!sourceId) return;
    const c = new AbortController();
    void api<Comparison>(
      `/api/cases/${caseId}/sources/${sourceId}/comparison`,
      { signal: c.signal },
    )
      .then(setComparison)
      .catch((e) => {
        if (!c.signal.aborted) setCompareError(message(e));
      });
    return () => c.abort();
  }, [caseId, sourceId]);
  async function control(action: string, body?: unknown) {
    setBusy(true);
    setError("");
    try {
      await post(`/api/investigations/${id}/${action}`, body);
      setRevision((n) => n + 1);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function openCitation(cid: string) {
    setError("");
    try {
      setCitation(
        await api<Citation>(
          `/api/cases/${caseId}/citations/${encodeURIComponent(cid)}`,
        ),
      );
    } catch (e) {
      setError(message(e));
    }
  }
  const currentComparison =
    comparison?.query_provenance.source_id === sourceId ? comparison : null;
  const top = currentComparison?.ranking[0],
    csvSources = report?.source_snapshot.filter((s) => s.kind === "csv") || [];
  const selectedSource = csvSources.find((s) => s.id === sourceId);
  const pdfReferences =
    report?.citations
      .filter((c) => c.citation_id.startsWith("pdf:"))
      .sort((a, b) => Number(b.cited_in_answer) - Number(a.cited_in_answer)) ||
    [];
  const active = run && !stopped.has(run.status),
    resumable = run && ["paused", "failed", "interrupted"].includes(run.status);
  const completed = run?.status === "completed";
  const extraTokens = run ? tokenContinuation(run) : null;
  const chartId = `chart-${id}`;
  return (
    <>
      <button className="ux-back ux-link" onClick={onBack}>
        <ArrowLeft size={17} />
        {t("Meine Untersuchungen")}
      </button>
      {loadedRun && !run ? (
        <div className="ux-error" role="alert">
          {t(
            "Diese Untersuchung gehört zu einem anderen Fall. Öffne sie unter Meine Untersuchungen.",
          )}
        </div>
      ) : !run ? (
        <p className="ux-loading">
          {connectionError || t("Untersuchung wird geöffnet…")}
        </p>
      ) : (
        <>
          <div className={`ux-complete ${completed ? "" : "pending"}`}>
            {completed ? (
              <Check size={18} />
            ) : active ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <Pause size={18} />
            )}
            <span>
              {completed
                ? run.result?.answer_contract?.outcome === "needs_review"
                  ? t("Prüfung erforderlich")
                  : run.result?.answer_contract?.outcome === "no_support"
                    ? t("Weitere Angaben erforderlich")
                    : run.chat_mode
                      ? t("Antwort bereit")
                      : t("Untersuchung abgeschlossen")
                : friendlyStatus(run.status)}
            </span>
          </div>
          <h1 className="ux-result-title">
            {completed
              ? run.result?.answer_contract?.outcome === "needs_review"
                ? t("Prüfe die Quellen der Antwort.")
                : run.result?.answer_contract?.outcome === "no_support"
                  ? t("Die ausgewählten Quellen belegen keine Antwort.")
                  : run.result?.capacity_limited
                    ? t("Bisherige Ergebnisse.")
                    : run.chat_mode
                      ? t("Deine Antwort.")
                      : t("Diese Änderungen wurden gefunden.")
              : active
                ? t("Belege werden geprüft.")
                : run.status === "paused"
                  ? t("Bereit für deine Frage.")
                  : t("Diese Untersuchung benötigt Aufmerksamkeit.")}
          </h1>
          <p className="ux-result-question">{run.question}</p>
          {!!run.result?.answer_contract?.issues.length && (
            <div className="ux-caution" role="alert">
              {run.result.answer_contract.issues.map(displayNotice).join(" ")}
            </div>
          )}
          {error && (
            <div className="ux-error" role="alert">
              {t(error)}
              <button
                className="ux-link"
                onClick={() => setRevision((n) => n + 1)}
              >
                {t("Erneut versuchen")}
              </button>
            </div>
          )}
          {!completed && (
            <section className="ux-progress-card" aria-live="polite">
              <div className="ux-progress-icon">
                {active ? (
                  <LoaderCircle className="spin" size={31} />
                ) : (
                  <FileText size={31} />
                )}
              </div>
              <h2>{progressText(run.status, events)}</h2>
              <p>
                {active
                  ? run.chat_mode
                    ? run.siemens
                      ? t(
                          "Du kannst diese Frage unter Meine Untersuchungen wieder öffnen. Die aktivierte Siemens-Suche sendet nur deine öffentliche Suchanfrage.",
                        )
                      : t(
                          "Du kannst diese Frage unter Meine Untersuchungen wieder öffnen. Die ausgewählte Bibliothek wird lokal durchsucht.",
                        )
                    : t(
                        "Du kannst die Seite verlassen und dieselbe Untersuchung später wieder öffnen. Deine Dateien bleiben auf diesem Computer.",
                      )
                  : run.status === "paused"
                    ? t(
                        "Dein Fortschritt ist gespeichert. Du kannst jederzeit fortsetzen.",
                      )
                    : extraTokens !== null
                      ? extraTokens
                        ? t(
                            "Dein Fortschritt ist gespeichert. Du kannst mit einer begrenzten zusätzlichen Kapazität fortsetzen; Dateien und andere Limits bleiben erhalten.",
                          )
                        : t(
                            "Dein Fortschritt ist gespeichert. Nutze das verbleibende Budget, ohne Dateien erneut hochzuladen.",
                          )
                      : run.error?.message ||
                        t(
                          "Die Untersuchung wurde beendet. Du kannst eine neue Frage zu denselben Dateien stellen.",
                        )}
              </p>
              <div className="ux-progress-actions">
                {active && (
                  <>
                    <button
                      className="ux-secondary"
                      onClick={() => void control("pause")}
                      disabled={busy}
                    >
                      <Pause size={17} />
                      {t("Pausieren")}
                    </button>
                    <button
                      className="ux-link"
                      onClick={() => void control("cancel")}
                      disabled={busy}
                    >
                      {t("Untersuchung abbrechen")}
                    </button>
                  </>
                )}
                {resumable && (
                  <>
                    <button
                      className="ux-primary"
                      onClick={() => void control("resume")}
                      disabled={busy}
                    >
                      <Play size={17} />
                      {t("Untersuchung fortsetzen")}
                    </button>
                    <button
                      className="ux-link"
                      onClick={() => void control("cancel")}
                      disabled={busy}
                    >
                      {t("Untersuchung abbrechen")}
                    </button>
                  </>
                )}
                {extraTokens !== null && (
                  <button
                    className="ux-primary"
                    disabled={busy}
                    onClick={() =>
                      void control("continue", {
                        additional_tokens: extraTokens,
                      })
                    }
                  >
                    <Play size={17} />
                    {continuationLabel(run, extraTokens)}
                  </button>
                )}
                {!active && !resumable && extraTokens === null && (
                  <button className="ux-primary" onClick={onAnother}>
                    {t("Weitere Frage stellen")}
                    <ArrowRight size={16} />
                  </button>
                )}
              </div>
              {connectionError && (
                <p className="ux-small">
                  {t(
                    "Verbindung unterbrochen. Wird neu verbunden; die gespeicherte Untersuchung bleibt unverändert.",
                  )}
                </p>
              )}
            </section>
          )}
          {!completed && !active && run.result?.capacity_limited && (
            <section className="ux-finding-card">
              <h2>{t("Teilweise Belegprüfung")}</h2>
              <SafeAnswer
                text={report?.answer || run.result.answer}
                references={[
                  ...(report?.citations || []),
                  ...(report?.library_citations || []),
                  ...(report?.problem_citations || []),
                ]}
              />
              {report && (
                <>
                  <AnswerReferences report={report} onOpen={openCitation} />
                  <LibraryReferences report={report} runId={id} />
                  <SiemensReferences report={report} />
                </>
              )}
            </section>
          )}
          {completed && !report && !error && (
            <p className="ux-loading">{t("Befunde werden vorbereitet…")}</p>
          )}
          {completed && report && (
            <>
              {run.result?.capacity_limited && (
                <p className="ux-caution">
                  {t(
                    "Dies ist eine Zusammenfassung der bisher gesammelten Belege. Weitere Prüfungen können erforderlich sein.",
                  )}
                </p>
              )}
              <section className="ux-finding-card">
                <span className="ux-section-label">{t("Hauptbefund")}</span>
                {csvSources.length > 1 && (
                  <label className="ux-data-select">
                    {t("Datendatei")}
                    <select
                      aria-label={t("Vergleichsdatendatei")}
                      value={sourceId}
                      onChange={(e) => setSourceId(e.target.value)}
                    >
                      {csvSources.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.filename}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {top ? (
                  <>
                    <h2>
                      {top.delta_percentage_points > 0
                        ? tr`Fehlausschuss stieg am stärksten bei ${top.station_id}`
                        : tr`Größte Stationsabweichung: ${top.station_id}`}
                    </h2>
                    <p>
                      {t("Die Quote")}{" "}
                      {top.incident_rate >= top.baseline_rate ? "rose" : "fell"}{" "}
                      from{" "}
                      <strong>{(top.baseline_rate * 100).toFixed(2)}%</strong>{" "}
                      to{" "}
                      <strong>{(top.incident_rate * 100).toFixed(2)}%</strong> —{" "}
                      {Math.abs(top.delta_percentage_points).toFixed(2)}{" "}
                      {t("Prozentpunkte")}{" "}
                      {top.delta_percentage_points >= 0 ? "higher" : "lower"}.
                    </p>
                    <div
                      className="ux-comparison"
                      role="img"
                      aria-labelledby={chartId}
                    >
                      <span id={chartId} className="ux-sr-only">
                        {top.station_id}
                        {t(": vorher")} {(top.baseline_rate * 100).toFixed(2)}
                        {t("%, im Störungszeitraum")}{" "}
                        {(top.incident_rate * 100).toFixed(2)}%
                      </span>
                      {[
                        [t("Vorher"), top.baseline_rate],
                        [t("Im Störungszeitraum"), top.incident_rate],
                      ].map(([label, value], i) => {
                        const max = Math.max(
                          top.baseline_rate,
                          top.incident_rate,
                          0.001,
                        );
                        const width = (Number(value) / max) * 490;
                        return (
                          <div className="ux-bar-row" key={String(label)}>
                            <span>{label}</span>
                            <svg
                              viewBox="0 0 490 28"
                              aria-hidden="true"
                              preserveAspectRatio="none"
                            >
                              <rect
                                x="0"
                                y="0"
                                width={width}
                                height="28"
                                rx="3"
                                className={i === 0 ? "ux-before" : "ux-during"}
                              />
                            </svg>
                            <strong>{(Number(value) * 100).toFixed(2)}%</strong>
                          </div>
                        );
                      })}
                    </div>
                    <p className="ux-calculated">
                      {t("Berechnet aus")} {selectedSource?.filename}
                      {t(". Separate Dateien werden unabhängig verglichen.")}
                    </p>
                    <div className="ux-source-pills">
                      {top.example_citations.map((cid, i) => (
                        <button
                          key={cid}
                          onClick={() => void openCitation(cid)}
                        >
                          <Table2 size={17} />
                          {i === 0
                            ? t("Vorher: Quellzeile")
                            : t("Störung: Quellzeile")}
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <>
                    <h2>
                      {compareError
                        ? t("Untersuchungsnotizen prüfen")
                        : run.chat_mode
                          ? t("Antwort")
                          : t("Was die Dateien zeigen")}
                    </h2>
                    <p className="ux-answer">
                      {readableAnswer(report.answer, [
                        ...report.citations,
                        ...(report.external_references || []),
                        ...(report.library_citations || []),
                      ]) || t("Kein abschließender Befund zurückgegeben.")}
                    </p>
                    {compareError && (
                      <p className="ux-small">
                        {t(
                          "Diese Datendatei konnte nicht verglichen werden. Der Berechnungsfehler steht in den erweiterten Details.",
                        )}
                      </p>
                    )}
                  </>
                )}
                {pdfReferences.length > 0 && (
                  <div className="ux-related">
                    <span className="ux-section-label">
                      {t("Zugehörige Belege")}
                    </span>
                    {pdfReferences.slice(0, 2).map((c) => (
                      <button
                        className="ux-excerpt"
                        key={c.citation_id}
                        onClick={() => void openCitation(c.citation_id)}
                      >
                        <span>{c.text}</span>
                        <small>
                          <FileText size={16} />
                          {c.filename} {t("· Seite")}{" "}
                          {(c.pages || [c.page]).join(", ")}
                          <ChevronDown size={14} />
                        </small>
                      </button>
                    ))}
                  </div>
                )}
                <div className="ux-caution">
                  {run.chat_mode
                    ? t("Vor der Anwendung die Quelldokumentation prüfen.")
                    : t("Ein zu prüfender Befund, keine bestätigte Ursache.")}
                </div>
              </section>
              {top && (
                <details className="ux-notes">
                  <summary>{t("Untersuchungsnotizen lesen")}</summary>
                  <p className="ux-answer">
                    {readableAnswer(report.answer, [
                      ...report.citations,
                      ...(report.external_references || []),
                      ...(report.library_citations || []),
                    ])}
                  </p>
                  <AnswerReferences report={report} onOpen={openCitation} />
                </details>
              )}
              {!report.citation_checks.has_answer_citations &&
                !report.external_references?.some((r) => r.cited_in_answer) &&
                !report.library_citations?.some((r) => r.cited_in_answer) &&
                report.answer && (
                  <p className="ux-source-warning">
                    {t(
                      "Die Notizen des Assistenten benötigen eine Quellenprüfung. Prüfe die Belege über die Quellenlinks, bevor du dich darauf stützt.",
                    )}
                  </p>
                )}
              <SiemensReferences report={report} />
              <LibraryReferences report={report} runId={id} />
              {!top && (
                <AnswerReferences report={report} onOpen={openCitation} />
              )}
              <div className="ux-next-check">
                <span className="ux-section-label">
                  {t("Nächster Schritt")}
                </span>
                <p>
                  {t("Prüfe vor einer Schlussfolgerung die verlinkten Belege.")}
                </p>
              </div>
              <div className="ux-result-actions">
                <button
                  className="ux-primary"
                  disabled={
                    Boolean(sourceId) && !currentComparison && !compareError
                  }
                  onClick={() =>
                    download(
                      `investigation-${id.slice(0, 8)}.html`,
                      userReport(
                        run,
                        report,
                        currentComparison,
                        selectedSource?.filename || "",
                      ),
                      "text/html",
                    )
                  }
                >
                  <ArrowDownToLine size={19} />
                  {t("Bericht herunterladen")}
                </button>
                <button className="ux-link" onClick={onAnother}>
                  {t("Weitere Frage stellen")}
                </button>
                <span>
                  {t(
                    "Lesbarer Bericht · Im Browser drucken oder als PDF speichern",
                  )}
                </span>
              </div>
            </>
          )}
          <details className="ux-advanced">
            <summary>{t("Erweiterte Details")}</summary>
            <p>
              {t(
                "Vollständigen Arbeitsbereich für Werkzeugaktivitäten, Quellenverweise, Berechnungsherkunft, Budgets und freigegebene Berichtsentwürfe öffnen.",
              )}
            </p>
            {compareError && <p>{compareError}</p>}
            <a href={advancedUrl(caseId, id)}>
              {t("Erweiterten Arbeitsbereich öffnen")}
              <ArrowRight size={15} />
            </a>
            <p className="ux-small">
              {t("Diese Untersuchung verwendete")}{" "}
              {(run.source_ids || []).length}{" "}
              {t(
                "gespeicherte Quelldatei(en). Später hinzugefügte Dateien werden nur für neue Untersuchungen verwendet.",
              )}
            </p>
          </details>
          <p className="ux-demo-note">
            {t(
              "Synthetische oder lizenzierte öffentliche Belege · Befunde vor der Nutzung prüfen",
            )}
          </p>
        </>
      )}
      {citation && (
        <Modal title={t("Quellbelege")} onClose={() => setCitation(null)} wide>
          <div className="ux-source-dialog">
            <h3>{citation.filename}</h3>
            <p>
              {citation.citation_id.startsWith("pdf:")
                ? tr`Seite ${(citation.pages || [citation.page]).join(", ")}`
                : tr`Quellzeile ${citation.row?.row_id} · CSV-Zeile ${citation.row?.csv_line}`}
            </p>
            {citation.text && <blockquote>{citation.text}</blockquote>}
            {citation.row && (
              <dl>
                {Object.entries(citation.row).map(([k, v]) => (
                  <div key={k}>
                    <dt>{k.replaceAll("_", " ")}</dt>
                    <dd>{String(v)}</dd>
                  </div>
                ))}
              </dl>
            )}
            <p className="ux-small">
              {t(
                "Dies ist eine Fundstelle, kein Beweis für die Richtigkeit einer Aussage.",
              )}
            </p>
            <a
              href={`/api/cases/${caseId}/sources/${citation.source_id}/file`}
              download
            >
              <ArrowDownToLine size={16} />
              {t("Originaldatei herunterladen")}
            </a>
          </div>
        </Modal>
      )}
      {detail && (
        <span className="ux-sr-only">
          {t("Untersuchung:")} {detail.title}
        </span>
      )}
    </>
  );
}

function AnswerReferences({
  report,
  onOpen,
}: {
  report: EvidenceReport;
  onOpen: (id: string) => Promise<void>;
}) {
  useLanguage();
  return (
    <div className="ux-source-pills ux-all-sources">
      {report.citations
        .filter((c) => c.cited_in_answer)
        .map((c) => (
          <button
            key={c.citation_id}
            onClick={() => void onOpen(c.citation_id)}
          >
            <FileText size={16} />
            {t("Quelle")} {report.citations.indexOf(c) + 1}: {c.filename}
          </button>
        ))}
    </div>
  );
}
