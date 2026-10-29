import { useEffect, useState } from "react";
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
import { tokenContinuation } from "./budgetRecovery";
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
    return "Searching your knowledge library…";
  if (last?.type === "siemens_lookup_started")
    return "Checking Siemens documentation…";
  if (name.includes("siemens")) return "Checking Siemens documentation…";
  if (name.includes("search") || name.includes("citation"))
    return "Reading your evidence…";
  if (name.includes("compare")) return "Checking the inspection data…";
  return "Reviewing your question and sources…";
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
        My investigations
      </button>
      {loadedRun && !run ? (
        <div className="ux-error" role="alert">
          This investigation belongs to a different case. Open it from My
          investigations.
        </div>
      ) : !run ? (
        <p className="ux-loading">
          {connectionError || "Opening your investigation…"}
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
                  ? "Review required"
                  : run.result?.answer_contract?.outcome === "no_support"
                    ? "More information needed"
                    : run.chat_mode
                      ? "Answer ready"
                      : "Investigation complete"
                : friendlyStatus(run.status)}
            </span>
          </div>
          <h1 className="ux-result-title">
            {completed
              ? run.result?.answer_contract?.outcome === "needs_review"
                ? "Review the answer sources."
                : run.result?.answer_contract?.outcome === "no_support"
                  ? "The selected sources do not establish an answer."
                  : run.result?.capacity_limited
                    ? "Here's what we found so far."
                    : run.chat_mode
                      ? "Here's your answer."
                      : "Here's what changed."
              : active
                ? "Following the evidence."
                : run.status === "paused"
                  ? "Ready when you are."
                  : "This investigation needs attention."}
          </h1>
          <p className="ux-result-question">{run.question}</p>
          {!!run.result?.answer_contract?.issues.length && (
            <div className="ux-caution" role="alert">
              {run.result.answer_contract.issues.join(" ")}
            </div>
          )}
          {error && (
            <div className="ux-error" role="alert">
              {error}
              <button
                className="ux-link"
                onClick={() => setRevision((n) => n + 1)}
              >
                Try again
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
                      ? "You can return to this question from My investigations. The enabled Siemens lookup sends only your public query."
                      : "You can return to this question from My investigations. Your selected library is searched locally."
                    : "You can leave this page and return to the same investigation. Your files stay on this computer."
                  : run.status === "paused"
                    ? "Your progress is saved. Resume whenever you are ready."
                    : extraTokens !== null
                      ? extraTokens
                        ? "Your progress is saved. Continue with one bounded allowance of extra capacity; your files and other limits stay in place."
                        : "Your progress is saved. Continue using the remaining allowance without uploading your files again."
                      : run.error?.message ||
                        "The investigation stopped. You can start another question with the same files."}
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
                      Pause
                    </button>
                    <button
                      className="ux-link"
                      onClick={() => void control("cancel")}
                      disabled={busy}
                    >
                      Cancel investigation
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
                      Resume investigation
                    </button>
                    <button
                      className="ux-link"
                      onClick={() => void control("cancel")}
                      disabled={busy}
                    >
                      Cancel investigation
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
                    {extraTokens
                      ? "Continue with extra capacity"
                      : "Continue investigation"}
                  </button>
                )}
                {!active && !resumable && extraTokens === null && (
                  <button className="ux-primary" onClick={onAnother}>
                    Ask another question
                    <ArrowRight size={16} />
                  </button>
                )}
              </div>
              {connectionError && (
                <p className="ux-small">
                  Connection interrupted. Reconnecting; your saved investigation
                  is unchanged.
                </p>
              )}
            </section>
          )}
          {completed && !report && !error && (
            <p className="ux-loading">Preparing your findings…</p>
          )}
          {completed && report && (
            <>
              {run.result?.capacity_limited && (
                <p className="ux-caution">
                  This is a summary of evidence gathered so far. Further checks
                  may still be needed.
                </p>
              )}
              <section className="ux-finding-card">
                <span className="ux-section-label">Main finding</span>
                {csvSources.length > 1 && (
                  <label className="ux-data-select">
                    Data file
                    <select
                      aria-label="Comparison data file"
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
                        ? `False rejects increased most at ${top.station_id}`
                        : `Highest station delta: ${top.station_id}`}
                    </h2>
                    <p>
                      The rate{" "}
                      {top.incident_rate >= top.baseline_rate ? "rose" : "fell"}{" "}
                      from{" "}
                      <strong>{(top.baseline_rate * 100).toFixed(2)}%</strong>{" "}
                      to{" "}
                      <strong>{(top.incident_rate * 100).toFixed(2)}%</strong> —{" "}
                      {Math.abs(top.delta_percentage_points).toFixed(2)}{" "}
                      percentage points{" "}
                      {top.delta_percentage_points >= 0 ? "higher" : "lower"}.
                    </p>
                    <div
                      className="ux-comparison"
                      role="img"
                      aria-labelledby={chartId}
                    >
                      <span id={chartId} className="ux-sr-only">
                        {top.station_id}: before{" "}
                        {(top.baseline_rate * 100).toFixed(2)}%, during incident{" "}
                        {(top.incident_rate * 100).toFixed(2)}%
                      </span>
                      {[
                        ["Before", top.baseline_rate],
                        ["During incident", top.incident_rate],
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
                      Calculated from {selectedSource?.filename}. Separate files
                      are compared independently.
                    </p>
                    <div className="ux-source-pills">
                      {top.example_citations.map((cid, i) => (
                        <button
                          key={cid}
                          onClick={() => void openCitation(cid)}
                        >
                          <Table2 size={17} />
                          {i === 0
                            ? "Before: source row"
                            : "During incident: source row"}
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <>
                    <h2>
                      {compareError
                        ? "Review the investigation notes"
                        : run.chat_mode
                          ? "Answer"
                          : "What the files tell us"}
                    </h2>
                    <p className="ux-answer">
                      {readableAnswer(report.answer, [
                        ...report.citations,
                        ...(report.external_references || []),
                        ...(report.library_citations || []),
                      ]) || "No final finding was returned."}
                    </p>
                    {compareError && (
                      <p className="ux-small">
                        This data file could not be compared. See Advanced
                        details for the calculation error.
                      </p>
                    )}
                  </>
                )}
                {pdfReferences.length > 0 && (
                  <div className="ux-related">
                    <span className="ux-section-label">Related evidence</span>
                    {pdfReferences.slice(0, 2).map((c) => (
                      <button
                        className="ux-excerpt"
                        key={c.citation_id}
                        onClick={() => void openCitation(c.citation_id)}
                      >
                        <span>{c.text}</span>
                        <small>
                          <FileText size={16} />
                          {c.filename} · page {(c.pages || [c.page]).join(", ")}
                          <ChevronDown size={14} />
                        </small>
                      </button>
                    ))}
                  </div>
                )}
                <div className="ux-caution">
                  {run.chat_mode
                    ? "Review the source documentation before applying this guidance."
                    : "A finding to verify, not a confirmed cause."}
                </div>
              </section>
              {top && (
                <details className="ux-notes">
                  <summary>Read investigation notes</summary>
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
                    The assistant's notes need a source check. Use the source
                    links to review the evidence before relying on them.
                  </p>
                )}
              <SiemensReferences report={report} />
              <LibraryReferences report={report} runId={id} />
              {!top && (
                <AnswerReferences report={report} onOpen={openCitation} />
              )}
              <div className="ux-next-check">
                <span className="ux-section-label">Next step</span>
                <p>
                  Review the linked source evidence before drawing a conclusion.
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
                  Download report
                </button>
                <button className="ux-link" onClick={onAnother}>
                  Ask another question
                </button>
                <span>
                  Readable report · print or save as PDF from your browser
                </span>
              </div>
            </>
          )}
          <details className="ux-advanced">
            <summary>Advanced details</summary>
            <p>
              Open the full workspace for tool activity, all source references,
              calculation provenance, limits, and approved report drafts.
            </p>
            {compareError && <p>{compareError}</p>}
            <a href={advancedUrl(caseId, id)}>
              Open advanced workspace
              <ArrowRight size={15} />
            </a>
            <p className="ux-small">
              This investigation used {(run.source_ids || []).length} saved
              source file(s). Files added later are used only by new
              investigations.
            </p>
          </details>
          <p className="ux-demo-note">
            Synthetic or licensed public evidence · Review findings before use
          </p>
        </>
      )}
      {citation && (
        <Modal title="Source evidence" onClose={() => setCitation(null)} wide>
          <div className="ux-source-dialog">
            <h3>{citation.filename}</h3>
            <p>
              {citation.citation_id.startsWith("pdf:")
                ? `Page ${(citation.pages || [citation.page]).join(", ")}`
                : `Source row ${citation.row?.row_id} · CSV line ${citation.row?.csv_line}`}
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
              This is a source location, not proof that a claim is correct.
            </p>
            <a
              href={`/api/cases/${caseId}/sources/${citation.source_id}/file`}
              download
            >
              <ArrowDownToLine size={16} />
              Download original file
            </a>
          </div>
        </Modal>
      )}
      {detail && (
        <span className="ux-sr-only">Investigation: {detail.title}</span>
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
            Source {report.citations.indexOf(c) + 1}: {c.filename}
          </button>
        ))}
    </div>
  );
}
