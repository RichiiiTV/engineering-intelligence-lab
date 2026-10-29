import { useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Beaker,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FilePlus2,
  FileText,
  FolderClosed,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  Pause,
  Play,
  Plus,
  Search,
  ShieldCheck,
  Square,
  Table2,
  Upload,
  Wrench,
} from "lucide-react";
import { api, download, post } from "./api";
import {
  CitationView,
  Empty,
  fmt,
  Json,
  Modal,
  StationChart,
  Status,
  Timeline,
  time,
} from "./components";
import { stopped, useInvestigation } from "./useInvestigation";
import { tokenContinuation } from "./budgetRecovery";
import type {
  Case,
  CaseDetail,
  Citation,
  Comparison,
  Draft,
  EvidenceReport,
  Hit,
  Proposal,
  Run,
  RunEvent,
  Source,
} from "./types";

const params = new URLSearchParams(location.search);
function remember(caseId: string, runId = "") {
  const query = new URLSearchParams();
  query.set("view", "advanced");
  query.set("case", caseId);
  if (runId) query.set("run", runId);
  history.replaceState(null, "", `/?${query}`);
  window.dispatchEvent(new Event("eil-selection"));
}
function simpleLocation() {
  const query = new URLSearchParams(location.search);
  query.delete("view");
  return `/?${query}`;
}
function errorText(e: unknown) {
  return e instanceof Error ? e.message : String(e);
}

export default function App() {
  const [simpleHref, setSimpleHref] = useState(simpleLocation);
  useEffect(() => {
    const update = () => setSimpleHref(simpleLocation());
    update();
    window.addEventListener("eil-selection", update);
    return () => window.removeEventListener("eil-selection", update);
  }, []);
  const [cases, setCases] = useState<Case[]>([]),
    [caseId, setCaseId] = useState(params.get("case") || "");
  const [newCase, setNewCase] = useState(false),
    [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [help, setHelp] = useState(false);
  async function loadCases() {
    try {
      const data = await api<{ cases: Case[] }>("/api/cases");
      setCases(data.cases);
    } catch (e) {
      setError(errorText(e));
    }
  }
  useEffect(() => {
    void loadCases();
  }, []);
  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const c = await post<Case>("/api/cases", { title: title.trim() });
      await loadCases();
      setCaseId(c.id);
      remember(c.id);
      setNewCase(false);
      setTitle("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="/?view=advanced"
          aria-label="Engineering Intelligence Lab home"
        >
          <span className="brand-mark">
            <Beaker size={22} />
          </span>
          <span>
            Engineering
            <br />
            <b>Intelligence Lab</b>
          </span>
        </a>
        <div className="workspace-label">
          <span className="workspace-avatar">RL</span>
          <span>
            Local workspace<small>Synthetic research environment</small>
          </span>
          <ChevronDown size={14} />
        </div>
        <div className="sidebar-heading">WORKSPACE</div>
        <div className="nav-item active">
          <LayoutDashboard size={17} />
          Investigations<span className="count">{cases.length}</span>
        </div>
        <div className="case-heading">
          <span>YOUR CASES</span>
          <button
            className="icon-button"
            aria-label="Create case"
            onClick={() => setNewCase(true)}
          >
            <Plus size={16} />
          </button>
        </div>
        <nav className="case-list" aria-label="Cases">
          {cases.map((c) => (
            <button
              key={c.id}
              className={`case-link ${caseId === c.id ? "selected" : ""}`}
              onClick={() => {
                setCaseId(c.id);
                remember(c.id);
              }}
            >
              <FolderClosed size={16} />
              <span>{c.title}</span>
              <ChevronRight size={13} />
            </button>
          ))}
        </nav>
        <button className="new-case-button" onClick={() => setNewCase(true)}>
          <Plus size={16} />
          New case
        </button>
        <div className="sidebar-bottom">
          <div className="local-card">
            <span className="online-dot" />
            <strong>Local by design</strong>
            <p>
              Read-only agents.
              <br />
              Your evidence stays here.
            </p>
          </div>
          <button className="help-button" onClick={() => setHelp(true)}>
            <CircleHelp size={17} />
            Workbench guide
            <ArrowRight size={14} />
          </button>
          <div className="build-label">
            EIL / MILESTONE 04<span>v0.4</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>
            Workspace <ChevronRight size={13} /> Investigations
          </span>
          <span className="environment">
            <a href={simpleHref}>Simple view</a>
            <span className="online-dot" />
            LOCAL DEMO
            <LockKeyhole size={13} />
          </span>
        </header>
        {error && !newCase && (
          <div className="banner error" role="alert">
            {error}
            <button onClick={() => setError("")}>Dismiss</button>
          </div>
        )}
        {caseId ? (
          <Workspace key={caseId} id={caseId} />
        ) : (
          <main className="welcome">
            <span className="eyebrow">ENGINEERING INTELLIGENCE LAB</span>
            <h1>
              Start with a question.
              <br />
              Build a case with evidence.
            </h1>
            <p>
              A local workbench for investigating inspection data, reviewing
              source documents, and developing traceable findings.
            </p>
            <button className="primary" onClick={() => setNewCase(true)}>
              <Plus size={17} />
              Create your first case
            </button>
            <div className="welcome-steps">
              <div>
                <span>01</span>
                <h3>Bring your evidence</h3>
                <p>Upload synthetic or licensed public CSV and PDF files.</p>
              </div>
              <div>
                <span>02</span>
                <h3>Follow the investigation</h3>
                <p>Inspect calculations, tool calls, and source citations.</p>
              </div>
              <div>
                <span>03</span>
                <h3>Review the findings</h3>
                <p>Approve a report draft and export the evidence record.</p>
              </div>
            </div>
          </main>
        )}
      </div>
      {newCase && (
        <Modal title="Create a case" onClose={() => setNewCase(false)}>
          <form onSubmit={create}>
            <p className="muted">
              Give this investigation a clear name. You can add evidence next.
            </p>
            <label htmlFor="case-title">Case name</label>
            <input
              id="case-title"
              autoFocus
              required
              maxLength={120}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. S03 inspection rate investigation"
            />
            {error && (
              <p className="error-text" role="alert">
                {error}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setNewCase(false)}
              >
                Cancel
              </button>
              <button className="primary" disabled={busy || !title.trim()}>
                {busy ? "Creating…" : "Create case"}
              </button>
            </div>
          </form>
        </Modal>
      )}
      {help && (
        <Modal
          title="Your investigation workbench"
          onClose={() => setHelp(false)}
        >
          <ol className="guide">
            <li>
              Create a case and upload inspection CSVs or text-based PDFs. Only
              synthetic or licensed public data is supported.
            </li>
            <li>
              Compare station rates and search documents in Overview. Open any
              citation to inspect its original location and source hash.
            </li>
            <li>
              Ask Ollama to investigate. Activity shows persistent tool
              arguments, observations, and checkpoints. Pause, resume, or cancel
              without resetting the run’s budgets.
            </li>
            <li>
              Review the model answer in Report. Edit a draft, preview the exact
              content, then approve its save. JSON exports include source
              snapshots and citation checks.
            </li>
          </ol>
          <p className="notice">
            The MCP option reads a fixed fictional maintenance dataset. No live
            systems are connected. Correlation does not establish causation.
          </p>
          <p>
            <a href="/api/examples/inspection.csv" download>
              Download sample CSV
            </a>{" "}
            ·{" "}
            <a href="/api/examples/maintenance.pdf" download>
              Download sample PDF
            </a>
          </p>
        </Modal>
      )}
    </div>
  );
}

function Workspace({ id }: { id: string }) {
  const [detail, setDetail] = useState<CaseDetail | null>(null),
    [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState(
    new URLSearchParams(location.search).get("run") || "",
  );
  const [revision, setRevision] = useState(0),
    [tab, setTab] = useState("overview");
  const {
    run: fetchedRun,
    events,
    error: streamError,
  } = useInvestigation(runId, revision);
  const run = fetchedRun?.case_id === id ? fetchedRun : null;
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false),
    [askOpen, setAskOpen] = useState(false);
  const [question, setQuestion] = useState(
    "Which station changed most between baseline and incident? Use the uploaded evidence, cite sources, and distinguish observations from hypotheses.",
  );
  const [useMcp, setUseMcp] = useState(false),
    [seconds, setSeconds] = useState(120);
  const [outputTokens, setOutputTokens] = useState(1024);
  const [sourceId, setSourceId] = useState(""),
    [comparison, setComparison] = useState<Comparison | null>(null);
  const [chartError, setChartError] = useState(""),
    [query, setQuery] = useState(""),
    [hits, setHits] = useState<Hit[] | null>(null);
  const [citation, setCitation] = useState<Citation | null>(null),
    [selectedEvent, setSelectedEvent] = useState<RunEvent | null>(null);
  const [report, setReport] = useState<EvidenceReport | null>(null),
    [drafts, setDrafts] = useState<Draft[]>([]),
    [proposals, setProposals] = useState<Proposal[]>([]);
  const [draftBody, setDraftBody] = useState(""),
    [draftTitle, setDraftTitle] = useState(""),
    [proposal, setProposal] = useState<Proposal | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      api<CaseDetail>(`/api/cases/${id}`, { signal: controller.signal }),
      api<{ investigations: Run[] }>(`/api/investigations?case_id=${id}`, {
        signal: controller.signal,
      }),
      api<{ drafts: Draft[]; proposals: Proposal[] }>(
        `/api/cases/${id}/drafts`,
        { signal: controller.signal },
      ),
    ])
      .then(([c, r, d]) => {
        setDetail(c);
        setRuns(r.investigations);
        setDrafts(d.drafts);
        setProposals(d.proposals);
        setSourceId(
          (previous) =>
            previous || c.sources.find((s) => s.kind === "csv")?.id || "",
        );
        setRunId((previous) =>
          r.investigations.some((x) => x.id === previous)
            ? previous
            : r.investigations[0]?.id || "",
        );
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      });
    return () => controller.abort();
  }, [id, revision]);
  useEffect(() => {
    setComparison(null);
    setChartError("");
    if (!sourceId) return;
    const controller = new AbortController();
    void api<Comparison>(`/api/cases/${id}/sources/${sourceId}/comparison`, {
      signal: controller.signal,
    })
      .then(setComparison)
      .catch((e) => {
        if (!controller.signal.aborted) setChartError(errorText(e));
      });
    return () => controller.abort();
  }, [id, sourceId]);
  useEffect(() => {
    setReport(null);
    setDraftBody("");
    setSelectedEvent(null);
    if (!run || !stopped.has(run.status)) return;
    const controller = new AbortController();
    void api<EvidenceReport>(`/api/investigations/${run.id}/export`, {
      signal: controller.signal,
    })
      .then((r) => {
        setReport(r);
        setDraftBody(r.answer);
        setDraftTitle(
          `${detail?.title || "Investigation"} — report`.slice(0, 120),
        );
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      });
    return () => controller.abort();
    // Case titles are immutable; waiting for the initial title avoids a loading race.
  }, [run?.id, run?.status, detail?.title]);
  useEffect(() => {
    remember(id, runId);
  }, [id, runId]);
  async function act(name: string, action: () => Promise<void>) {
    setBusy(name);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy("");
    }
  }
  function viewCitation(cid: string) {
    void act("citation", async () =>
      setCitation(
        await api<Citation>(
          `/api/cases/${id}/citations/${encodeURIComponent(cid)}`,
        ),
      ),
    );
  }
  async function start(e: FormEvent) {
    e.preventDefault();
    await act("start", async () => {
      const r = await post<Run>("/api/investigations", {
        case_id: id,
        question,
        use_mock_mcp: useMcp,
        limits: { timeout_seconds: seconds, max_output_tokens: outputTokens },
      });
      setRunId(r.id);
      setAskOpen(false);
      setTab("activity");
      setRevision((x) => x + 1);
    });
  }
  function control(action: string) {
    void act(action, async () => {
      await post(`/api/investigations/${runId}/${action}`);
      setRevision((x) => x + 1);
    });
  }
  async function search(e: FormEvent) {
    e.preventDefault();
    await act("search", async () => {
      const r = await api<{ hits: Hit[] }>(
        `/api/cases/${id}/search?q=${encodeURIComponent(query)}`,
      );
      setHits(r.hits);
    });
  }
  async function previewDraft() {
    await act("proposal", async () => {
      setProposal(
        await post<Proposal>(`/api/investigations/${runId}/draft-proposals`, {
          title: draftTitle,
          body: draftBody,
        }),
      );
      setRevision((x) => x + 1);
    });
  }
  async function decide(decision: "approve" | "reject") {
    if (!proposal) return;
    await act("decision", async () => {
      await post(`/api/approvals/${proposal.id}/decision`, {
        decision,
        expected_sha256: proposal.sha256,
      });
      setProposal(null);
      setRevision((x) => x + 1);
      setMessage(
        decision === "approve"
          ? "Report draft approved and saved."
          : "Proposal rejected. No draft was saved.",
      );
    });
  }
  const sources = detail?.sources || [],
    csvSources = sources.filter((s) => s.kind === "csv");
  const active = !!run && !stopped.has(run.status),
    top = comparison?.ranking[0];
  const elapsed = run
    ? run.elapsed_seconds +
      (active && run.attempt_started_at
        ? Math.max(0, (Date.now() - Date.parse(run.attempt_started_at)) / 1000)
        : 0)
    : 0;
  if (!detail)
    return (
      <main className="content">
        <p className="muted">{error || "Loading case…"}</p>
      </main>
    );
  return (
    <main className="content">
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            CASE WORKSPACE <span className="tiny-separator">/</span>{" "}
            {id.slice(0, 8).toUpperCase()}
          </div>
          <h1>{detail.title}</h1>
          <p>Bring the data together. Follow the evidence.</p>
        </div>
        <button
          className="primary"
          onClick={() => setAskOpen(true)}
          disabled={!sources.length || !!busy}
        >
          <Plus size={17} />
          New investigation
        </button>
      </div>
      {error && (
        <div className="banner error" role="alert">
          {error}
          <button onClick={() => setError("")}>Dismiss</button>
        </div>
      )}
      {message && (
        <div className="banner success" role="status">
          <Check size={16} />
          {message}
        </div>
      )}
      <div className="case-meta">
        <span>
          <FolderClosed size={14} />
          Created{" "}
          {new Date(detail.created_at).toLocaleDateString([], {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </span>
        <span>
          <ShieldCheck size={14} />
          Read-only investigation
        </span>
        <span>
          <BookOpen size={14} />
          {sources.length} evidence sources
        </span>
      </div>
      <div className="tabs-and-run">
        <div className="tabs" role="tablist" aria-label="Case views">
          {[
            ["overview", LayoutDashboard, "Overview"],
            ["activity", Activity, "Activity"],
            ["report", FileText, "Report"],
          ].map(([value, Icon, label]) => {
            const TabIcon = Icon as typeof Activity;
            return (
              <button
                key={String(value)}
                role="tab"
                aria-selected={tab === value}
                onClick={() => setTab(String(value))}
              >
                <TabIcon size={16} />
                {String(label)}
                {value === "activity" && active && <i className="online-dot" />}
              </button>
            );
          })}
        </div>
        <div className="run-select">
          <label htmlFor="run-select">Investigation</label>
          <select
            id="run-select"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
          >
            <option value="">Select a run</option>
            {runs.map((r) => (
              <option value={r.id} key={r.id}>
                {time(r.created_at)} · {r.question.slice(0, 40)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {run && (
        <div className="run-strip">
          <Status value={run.status} />
          <span className="run-question" title={run.question}>
            {run.question}
          </span>
          <div className="run-actions">
            {tokenContinuation(run) !== null && (
              <button
                className="secondary compact"
                disabled={!!busy}
                onClick={() =>
                  void act("continue", async () => {
                    await post(`/api/investigations/${run.id}/continue`, {
                      additional_tokens: tokenContinuation(run),
                    });
                    setRevision((x) => x + 1);
                  })
                }
              >
                <Play size={14} />
                Continue{tokenContinuation(run) ? " with extra capacity" : ""}
              </button>
            )}
            {active && (
              <>
                <button
                  className="secondary compact"
                  onClick={() => control("pause")}
                  disabled={!!busy}
                >
                  <Pause size={14} />
                  Pause
                </button>
                <button
                  className="icon-button"
                  onClick={() => control("cancel")}
                  disabled={!!busy}
                  aria-label="Cancel investigation"
                >
                  <Square size={14} />
                </button>
              </>
            )}
            {["paused", "interrupted", "failed"].includes(run.status) && (
              <>
                <button
                  className="secondary compact"
                  onClick={() => control("resume")}
                  disabled={!!busy}
                >
                  <Play size={14} />
                  Resume
                </button>
                <button
                  className="secondary compact"
                  onClick={() => control("cancel")}
                  disabled={!!busy}
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>
      )}
      {run?.error && (
        <div className="banner error" role="alert">
          {run.error.message || JSON.stringify(run.error)}
        </div>
      )}
      {tab === "overview" && (
        <>
          <div className="stat-grid">
            <div className="stat">
              <span>
                Evidence sources
                <FileText size={16} />
              </span>
              <strong>{sources.length.toString().padStart(2, "0")}</strong>
              <small>
                {csvSources.length} CSV ·{" "}
                {sources.filter((s) => s.kind === "pdf").length} PDF
              </small>
            </div>
            <div className="stat">
              <span>
                Stations compared
                <Table2 size={16} />
              </span>
              <strong>
                {comparison?.ranking.length.toString().padStart(2, "0") || "—"}
              </strong>
              <small>Baseline against incident</small>
            </div>
            <div className="stat">
              <span>
                Highest station delta
                <Activity size={16} />
              </span>
              <strong>
                {top
                  ? `${top.delta_percentage_points > 0 ? "+" : ""}${top.delta_percentage_points.toFixed(2)}`
                  : "—"}
                <em>{top ? " pp" : ""}</em>
              </strong>
              <small>
                {top
                  ? `${top.station_id} · descriptive finding`
                  : "Upload a CSV to compare"}
              </small>
            </div>
          </div>
          <div className="overview-grid">
            <div className="left-column">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Station performance</h2>
                    <p>
                      Compare false-ejection rates across inspection stations.
                    </p>
                  </div>
                  <span className="subtle-tag">CSV ANALYSIS</span>
                </div>
                {csvSources.length > 0 && (
                  <label className="source-select">
                    Source
                    <select
                      aria-label="Chart CSV source"
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
                {comparison ? (
                  <StationChart data={comparison} onCitation={viewCitation} />
                ) : (
                  <Empty title={chartError || "No station data yet"}>
                    Upload an inspection CSV to calculate baseline and incident
                    rates.
                  </Empty>
                )}
              </section>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Search the documents</h2>
                    <p>Find excerpts with traceable page references.</p>
                  </div>
                  <BookOpen size={19} />
                </div>
                <form className="search-form" onSubmit={search}>
                  <Search size={17} />
                  <input
                    aria-label="Document search"
                    placeholder="Search evidence, e.g. illumination exposure…"
                    value={query}
                    maxLength={500}
                    onChange={(e) => setQuery(e.target.value)}
                    required
                  />
                  <button
                    className="secondary compact"
                    disabled={!!busy || !query.trim()}
                  >
                    Search
                  </button>
                </form>
                {hits === null ? (
                  <p className="hint">
                    Searches this case’s PDFs using literal words. Relevance is
                    not factual confidence.
                  </p>
                ) : hits.length ? (
                  <div className="search-hits">
                    {hits.map((h) => (
                      <button
                        key={h.citation_id}
                        className="search-hit"
                        onClick={() => viewCitation(h.citation_id)}
                      >
                        <span>
                          {h.filename}
                          <b>Page {(h.pages || [h.page]).join(", ")}</b>
                        </span>
                        <p>{h.text}</p>
                        <small>
                          Inspect citation <ArrowRight size={13} />
                        </small>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="hint">
                    No matching excerpts. An empty result is not proof of
                    absence.
                  </p>
                )}
              </section>
            </div>
            <aside className="right-column">
              <section className="panel evidence-panel">
                <div className="panel-heading">
                  <h2>Evidence library</h2>
                  <span className="count">{sources.length}</span>
                </div>
                <div className="source-list">
                  {sources.map((s) => (
                    <SourceRow key={s.id} source={s} caseId={id} />
                  ))}
                  {!sources.length && (
                    <Empty title="Add your first source">
                      Build the case with inspection data and supporting
                      documents.
                    </Empty>
                  )}
                </div>
                <button
                  className="upload-button"
                  onClick={() => setUploadOpen(true)}
                >
                  <Upload size={16} />
                  Upload evidence
                </button>
                <p className="hint">
                  PDF up to 10 MiB · CSV up to 2 MiB
                  <br />
                  Synthetic or licensed public data only.
                </p>
              </section>
              <section className="insight-card">
                <span className="eyebrow">
                  <ShieldCheck size={14} />
                  EVIDENCE BEFORE INFERENCE
                </span>
                <h3>A finding is a starting point.</h3>
                <p>
                  Concurrent changes can suggest a hypothesis. They do not prove
                  the cause. Review original sources and define the next check.
                </p>
              </section>
              <div className="mock-note">
                <Wrench size={16} />
                <div>
                  <strong>MCP sandbox</strong>
                  <p>
                    {run?.use_mock_mcp
                      ? "Mock enabled for the selected run."
                      : "Optional local mock. Enable when starting a run."}{" "}
                    No live systems connected.
                  </p>
                </div>
              </div>
            </aside>
          </div>
        </>
      )}
      {tab === "activity" &&
        (run ? (
          <>
            <div className="budget-bar">
              <span>
                <b>
                  {run.model_calls}/{run.limits.max_model_calls}
                </b>{" "}
                model calls
              </span>
              <span>
                <b>
                  {run.tool_calls}/{run.limits.max_tool_calls}
                </b>{" "}
                tool calls
              </span>
              <span>
                <b>
                  {fmt(run.tokens)}/{fmt(run.limits.max_total_tokens)}
                </b>{" "}
                tokens
              </span>
              <span>
                <b>
                  {elapsed.toFixed(1)}/{run.limits.timeout_seconds}s
                </b>{" "}
                active time
              </span>
              <span>
                <b>
                  {run.steps}/{run.limits.max_steps}
                </b>{" "}
                steps
              </span>
            </div>
            {streamError && (
              <p className="notice">
                Event connection: {streamError}. Reconnecting automatically
                while the run is active.
              </p>
            )}
            <div className="activity-grid">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Investigation timeline</h2>
                    <p>Persisted events · {events.length} recorded</p>
                  </div>
                  {active && <LoaderCircle className="spin" size={17} />}
                </div>
                <Timeline
                  events={events}
                  selected={selectedEvent?.id || null}
                  onSelect={setSelectedEvent}
                />
              </section>
              <section className="panel tool-detail">
                <div className="panel-heading">
                  <div>
                    <h2>Event details</h2>
                    <p>Inspect tool arguments and returned observations.</p>
                  </div>
                  <Wrench size={18} />
                </div>
                {selectedEvent ? (
                  <>
                    <span className="subtle-tag">
                      {selectedEvent.type.replaceAll("_", " ")}
                    </span>
                    <p className="muted small">
                      {time(selectedEvent.at)} · event {selectedEvent.id}
                    </p>
                    {selectedEvent.data.tool_call_id && (
                      <>
                        <label>Tool call</label>
                        <code className="break">
                          {String(selectedEvent.data.tool_call_id)}
                        </code>
                      </>
                    )}
                    {selectedEvent.type === "tool_finished" && (
                      <>
                        <label>Arguments</label>
                        <Json
                          value={
                            events.find(
                              (e) =>
                                e.type === "tool_requested" &&
                                e.data.tool_call_id ===
                                  selectedEvent.data.tool_call_id,
                            )?.data.arguments || {}
                          }
                        />
                        <label>Observation</label>
                      </>
                    )}
                    <Json
                      value={
                        selectedEvent.data.observation || selectedEvent.data
                      }
                    />
                  </>
                ) : (
                  <Empty title="Select an event">
                    Open a tool call to review its inputs and evidence.
                  </Empty>
                )}
              </section>
            </div>
          </>
        ) : (
          <Empty title="No investigation selected">
            Start an investigation to see the agent’s activity.
          </Empty>
        ))}
      {tab === "report" && (
        <div className="report-grid">
          <section className="panel report-panel">
            <div className="panel-heading">
              <div>
                <h2>Investigation report</h2>
                <p>Model findings · review against the cited evidence.</p>
              </div>
              {report && (
                <button
                  className="secondary compact"
                  onClick={() =>
                    void act("export", async () => {
                      const full = await api<unknown>(
                        `/api/investigations/${runId}/export`,
                      );
                      download(
                        `eil-report-${runId.slice(0, 8)}.json`,
                        JSON.stringify(full, null, 2),
                      );
                    })
                  }
                >
                  <ArrowDownToLine size={15} />
                  Export JSON
                </button>
              )}
            </div>
            {report?.answer ? (
              <>
                <div className="report-answer">{report.answer}</div>
                <p className="notice">
                  Correlation does not establish causation. Citation resolution
                  checks source location, not claim validity.
                </p>
                <h3>Source citations</h3>
                {!report.citation_checks.has_answer_citations && (
                  <p className="notice">
                    The answer contains no recognized case citations.
                  </p>
                )}
                {(report.citation_checks.unresolved.length > 0 ||
                  report.citation_checks.malformed.length > 0 ||
                  report.citation_checks.not_returned_by_tools.length > 0) && (
                  <details open className="notice">
                    <summary>Citations need review</summary>
                    <Json value={report.citation_checks} />
                  </details>
                )}
                <div className="citation-list">
                  {report.citations.map((c) => (
                    <button
                      key={c.citation_id}
                      onClick={() => viewCitation(c.citation_id)}
                    >
                      <FileText size={16} />
                      <span>
                        {c.filename}
                        <small>
                          {c.citation_id.startsWith("pdf:")
                            ? `Page ${(c.pages || [c.page]).join(", ")}`
                            : `Row ${c.row?.row_id} · line ${c.row?.csv_line}`}{" "}
                          ·{" "}
                          {c.cited_in_answer
                            ? "Cited in answer"
                            : "Returned by tool"}
                        </small>
                      </span>
                      <ChevronRight size={15} />
                    </button>
                  ))}
                </div>
                <details className="method">
                  <summary>Uncertainty & limitations</summary>
                  <ul>
                    {report.uncertainty.limitations.map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                  </ul>
                </details>
              </>
            ) : (
              <Empty
                title={active ? "Investigation in progress" : "No findings yet"}
              >
                {active
                  ? "Review the agent’s progress in Activity. Findings appear here when the run stops."
                  : "Complete an investigation to review and export its findings."}
              </Empty>
            )}
          </section>
          <section className="panel draft-panel">
            <div className="panel-heading">
              <div>
                <h2>Report draft</h2>
                <p>Review, edit, then approve a save.</p>
              </div>
              <FilePlus2 size={19} />
            </div>
            {run?.status === "completed" && report?.answer ? (
              <>
                <label htmlFor="draft-title">Title</label>
                <input
                  id="draft-title"
                  maxLength={120}
                  value={draftTitle}
                  onChange={(e) => setDraftTitle(e.target.value)}
                />
                <label htmlFor="draft-body">Draft text</label>
                <textarea
                  id="draft-body"
                  rows={16}
                  maxLength={20000}
                  value={draftBody}
                  onChange={(e) => setDraftBody(e.target.value)}
                />
                <p className="hint">
                  Edits stay in this browser until you request a review. A
                  separate approval saves the exact previewed content.
                </p>
                <button
                  className="primary full"
                  onClick={() => void previewDraft()}
                  disabled={!!busy || !draftBody.trim() || !draftTitle.trim()}
                >
                  <ShieldCheck size={16} />
                  Review draft for approval
                </button>
              </>
            ) : (
              <p className="muted">
                A completed investigation is required to prepare a draft.
              </p>
            )}
            {proposals.filter((p) => p.status === "pending").length > 0 && (
              <div className="saved-drafts">
                <h3>Pending approvals</h3>
                {proposals
                  .filter((p) => p.status === "pending")
                  .map((p) => (
                    <button
                      className="saved-draft"
                      key={p.id}
                      onClick={() => setProposal(p)}
                    >
                      <ShieldCheck size={15} />
                      <span>
                        {p.title}
                        <small>Awaiting your review</small>
                      </span>
                      <ChevronRight size={15} />
                    </button>
                  ))}
              </div>
            )}
            {drafts.length > 0 && (
              <div className="saved-drafts">
                <h3>Approved drafts</h3>
                {drafts.map((d) => (
                  <button
                    className="saved-draft"
                    key={d.id}
                    onClick={() =>
                      download(
                        `eil-draft-${d.id.slice(0, 8)}.md`,
                        `# ${d.title}\n\n${d.body}\n\n---\nRun: ${d.run_id}\nApproved proposal: ${d.proposal_id}\nContent SHA-256: ${d.sha256}\n\nExperimental findings; review evidence. Correlation does not establish causation.\n`,
                        "text/markdown",
                      )
                    }
                  >
                    <Check size={15} />
                    <span>
                      {d.title}
                      <small>Approved · download Markdown</small>
                    </span>
                    <ArrowDownToLine size={15} />
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
      <footer className="page-footer">
        <span>
          <Beaker size={13} /> Engineering Intelligence Lab
        </span>
        <span>Local research · Synthetic evidence · Human judgment</span>
      </footer>
      {uploadOpen && (
        <UploadModal
          id={id}
          onClose={() => setUploadOpen(false)}
          onDone={() => {
            setUploadOpen(false);
            setRevision((x) => x + 1);
            setMessage(
              "Evidence uploaded and available to new investigations.",
            );
          }}
        />
      )}
      {askOpen && (
        <Modal title="Start an investigation" onClose={() => setAskOpen(false)}>
          <form onSubmit={start}>
            <label htmlFor="question">Investigation question</label>
            <textarea
              autoFocus
              id="question"
              rows={5}
              required
              maxLength={4000}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <p className="hint">
              This run uses a fixed snapshot of the {sources.length} current
              evidence source(s).
            </p>
            <label htmlFor="timeout">Active time budget (seconds)</label>
            <input
              id="timeout"
              type="number"
              min={1}
              max={600}
              required
              value={seconds}
              onChange={(e) => setSeconds(Number(e.target.value))}
            />
            <p className="hint">
              8 model calls · 16 tool calls · 32,768 tokens · 35 steps. Budgets
              persist across pause and resume.
            </p>
            <label htmlFor="output-tokens">
              Maximum output tokens per model call
            </label>
            <select
              id="output-tokens"
              value={outputTokens}
              onChange={(e) => setOutputTokens(Number(e.target.value))}
            >
              <option value={1024}>1,024 (default)</option>
              <option value={2048}>2,048 (longer reasoning / answers)</option>
            </select>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={useMcp}
                onChange={(e) => setUseMcp(e.target.checked)}
              />
              <span>
                Allow read-only mock MCP context
                <small>
                  Fixed local synthetic maintenance server. No case files are
                  sent. This run can read fictional station notes.
                </small>
              </span>
            </label>
            {error && (
              <p className="error-text" role="alert">
                {error}
              </p>
            )}
            <div className="modal-actions">
              <button
                className="secondary"
                type="button"
                onClick={() => setAskOpen(false)}
              >
                Cancel
              </button>
              <button className="primary" disabled={!!busy || !question.trim()}>
                <Play size={15} />
                {busy === "start" ? "Starting…" : "Start investigation"}
              </button>
            </div>
          </form>
        </Modal>
      )}
      {citation && (
        <Modal
          title="Evidence reference"
          onClose={() => setCitation(null)}
          wide
        >
          <CitationView citation={citation} />
        </Modal>
      )}
      {proposal && (
        <Modal
          title="Approve report draft"
          onClose={() => setProposal(null)}
          wide
        >
          <div className="approval-notice">
            <ShieldCheck size={20} />
            <div>
              <strong>This action will save a report draft.</strong>
              <p>
                Review the full content below. Approval saves this exact version
                to this case. It does not validate its claims.
              </p>
            </div>
          </div>
          <h3>{proposal.title}</h3>
          <div className="approval-preview">{proposal.body}</div>
          <label>Content SHA-256</label>
          <code className="break">{proposal.sha256}</code>
          {error && (
            <p className="error-text" role="alert">
              {error}
            </p>
          )}
          <div className="modal-actions">
            <button
              className="secondary"
              onClick={() => void decide("reject")}
              disabled={!!busy}
            >
              Reject proposal
            </button>
            <button
              className="primary"
              onClick={() => void decide("approve")}
              disabled={!!busy}
            >
              <Check size={16} />
              {busy === "decision" ? "Saving…" : "Approve & save draft"}
            </button>
          </div>
        </Modal>
      )}
    </main>
  );
}

function SourceRow({ source, caseId }: { source: Source; caseId: string }) {
  const Icon = source.kind === "csv" ? Table2 : FileText;
  return (
    <details className="source-row">
      <summary>
        <span className={`file-icon ${source.kind}`}>
          <Icon size={18} />
        </span>
        <span className="source-name">
          {source.filename}
          <small>
            {source.kind.toUpperCase()} ·{" "}
            {source.row_count
              ? `${fmt(source.row_count)} rows`
              : `${source.page_count} pages`}
          </small>
        </span>
        <ChevronDown size={14} />
      </summary>
      <div className="source-info">
        <p>
          {source.data_policy} · {(source.size / 1024).toFixed(1)} KiB
        </p>
        <label>SHA-256</label>
        <code className="break">{source.sha256}</code>
        <a href={`/api/cases/${caseId}/sources/${source.id}/file`} download>
          <ArrowDownToLine size={13} />
          Download original
        </a>
      </div>
    </details>
  );
}
function UploadModal({
  id,
  onClose,
  onDone,
}: {
  id: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [file, setFile] = useState<File | null>(null),
    [policy, setPolicy] = useState("synthetic"),
    [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    if (!/\.(pdf|csv)$/i.test(file.name)) {
      setError("Choose a PDF or CSV file.");
      return;
    }
    const max = /\.pdf$/i.test(file.name) ? 10 : 2;
    if (file.size > max * 1024 * 1024) {
      setError(`This file exceeds the ${max} MiB limit.`);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.set("file", file);
      data.set("data_policy", policy);
      await api(`/api/cases/${id}/sources`, { method: "POST", body: data });
      onDone();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Upload evidence" onClose={onClose}>
      <form onSubmit={upload}>
        <p className="muted">
          Sources are immutable and isolated to this case. New uploads are
          available to new investigations.
        </p>
        <label className="file-drop" htmlFor="evidence-file">
          <Upload size={25} />
          <strong>{file?.name || "Choose a PDF or CSV"}</strong>
          <span>PDF up to 10 MiB / 20 pages · CSV up to 2 MiB</span>
          <input
            id="evidence-file"
            type="file"
            accept=".csv,.pdf"
            required
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
        <label htmlFor="data-policy">Data category</label>
        <select
          id="data-policy"
          value={policy}
          onChange={(e) => setPolicy(e.target.value)}
        >
          <option value="synthetic">Synthetic / generated demo data</option>
          <option value="licensed-public">
            Explicitly licensed public data
          </option>
        </select>
        <label className="checkbox-label">
          <input
            type="checkbox"
            required
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          <span>
            I confirm this file belongs to the selected data category and
            contains no internal or sensitive information.
          </span>
        </label>
        <p className="hint">
          PDF conversion runs locally with OCR disabled. Scanned PDFs may have
          no extractable text.
        </p>
        <p className="hint">
          <a href="/api/examples/inspection.csv" download>
            Sample CSV
          </a>{" "}
          ·{" "}
          <a href="/api/examples/maintenance.pdf" download>
            Sample PDF
          </a>
        </p>
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="primary" disabled={busy || !file || !confirmed}>
            {busy ? (
              <>
                <LoaderCircle className="spin" size={16} />
                Processing locally…
              </>
            ) : (
              <>
                <Upload size={16} />
                Upload evidence
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
