import { useLanguage, t, tr, getLocale } from "./i18n";
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
  useLanguage();
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
          aria-label={t("Startseite von Engineering Intelligence Lab")}
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
            {t("Lokaler Arbeitsbereich")}
            <small>{t("Synthetische Forschungsumgebung")}</small>
          </span>
          <ChevronDown size={14} />
        </div>
        <div className="sidebar-heading">{t("ARBEITSBEREICH")}</div>
        <div className="nav-item active">
          <LayoutDashboard size={17} />
          {t("Untersuchungen")}
          <span className="count">{cases.length}</span>
        </div>
        <div className="case-heading">
          <span>{t("DEINE FÄLLE")}</span>
          <button
            className="icon-button"
            aria-label={t("Fall erstellen")}
            onClick={() => setNewCase(true)}
          >
            <Plus size={16} />
          </button>
        </div>
        <nav className="case-list" aria-label={t("Fälle")}>
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
          {t("Neuer Fall")}
        </button>
        <div className="sidebar-bottom">
          <div className="local-card">
            <span className="online-dot" />
            <strong>{t("Lokal konzipiert")}</strong>
            <p>
              {t("Agenten mit rein lesendem Zugriff.")}
              <br />
              {t("Deine Daten bleiben hier.")}
            </p>
          </div>
          <button className="help-button" onClick={() => setHelp(true)}>
            <CircleHelp size={17} />
            {t("Anleitung zum Arbeitsbereich")}
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
            {t("Arbeitsbereich")} <ChevronRight size={13} />{" "}
            {t("Untersuchungen")}
          </span>
          <span className="environment">
            <a href={simpleHref}>{t("Einfache Ansicht")}</a>
            <span className="online-dot" />
            {t("LOKALE DEMO")}
            <LockKeyhole size={13} />
          </span>
        </header>
        {error && !newCase && (
          <div className="banner error" role="alert">
            {t(error)}
            <button onClick={() => setError("")}>{t("Schließen")}</button>
          </div>
        )}
        {caseId ? (
          <Workspace key={caseId} id={caseId} />
        ) : (
          <main className="welcome">
            <span className="eyebrow">ENGINEERING INTELLIGENCE LAB</span>
            <h1>
              {t("Beginne mit einer Frage.")}
              <br />
              {t("Untersuche einen Fall anhand von Belegen.")}
            </h1>
            <p>
              {t(
                "Ein lokaler Arbeitsbereich für die Analyse von Prüfdaten, Quelldokumenten und nachvollziehbaren Ergebnissen.",
              )}
            </p>
            <button className="primary" onClick={() => setNewCase(true)}>
              <Plus size={17} />
              {t("Ersten Fall erstellen")}
            </button>
            <div className="welcome-steps">
              <div>
                <span>01</span>
                <h3>{t("Daten hinzufügen")}</h3>
                <p>
                  {t(
                    "Synthetische oder lizenzierte öffentliche CSV- und PDF-Dateien hochladen.",
                  )}
                </p>
              </div>
              <div>
                <span>02</span>
                <h3>{t("Untersuchung verfolgen")}</h3>
                <p>
                  {t(
                    "Berechnungen, Werkzeugaufrufe und Quellenangaben prüfen.",
                  )}
                </p>
              </div>
              <div>
                <span>03</span>
                <h3>{t("Ergebnisse prüfen")}</h3>
                <p>
                  {t(
                    "Berichtsentwurf freigeben und Belegübersicht exportieren.",
                  )}
                </p>
              </div>
            </div>
          </main>
        )}
      </div>
      {newCase && (
        <Modal title={t("Fall erstellen")} onClose={() => setNewCase(false)}>
          <form onSubmit={create}>
            <p className="muted">
              {t(
                "Gib dieser Untersuchung einen eindeutigen Namen. Belege kannst du anschließend hinzufügen.",
              )}
            </p>
            <label htmlFor="case-title">{t("Fallname")}</label>
            <input
              id="case-title"
              autoFocus
              required
              maxLength={120}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("z. B. Untersuchung der Prüfquote S03")}
            />
            {error && (
              <p className="error-text" role="alert">
                {t(error)}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setNewCase(false)}
              >
                {t("Abbrechen")}
              </button>
              <button className="primary" disabled={busy || !title.trim()}>
                {busy ? t("Wird erstellt…") : t("Fall erstellen")}
              </button>
            </div>
          </form>
        </Modal>
      )}
      {help && (
        <Modal
          title={t("Dein Untersuchungsbereich")}
          onClose={() => setHelp(false)}
        >
          <ol className="guide">
            <li>
              {t(
                "Erstelle einen Fall und lade Prüf-CSV-Dateien oder textbasierte PDFs hoch. Hier werden nur synthetische oder lizenzierte öffentliche Daten unterstützt.",
              )}
            </li>
            <li>
              {t(
                "Vergleiche Stationsquoten und durchsuche Dokumente in der Übersicht. Öffne Quellenangaben, um die Originalstelle und Prüfsumme zu sehen.",
              )}
            </li>
            <li>
              {t(
                "Lass Ollama untersuchen. Unter Aktivitäten siehst du gespeicherte Werkzeugargumente, Beobachtungen und Checkpoints. Pausieren, Fortsetzen und Abbrechen setzen keine Budgets zurück.",
              )}
            </li>
            <li>
              {t(
                "Prüfe die Modellantwort im Bericht. Bearbeite einen Entwurf, prüfe die genaue Vorschau und gib das Speichern frei. JSON-Exporte enthalten Quellstände und Quellenprüfungen.",
              )}
            </li>
          </ol>
          <p className="notice">
            {t(
              "Die MCP-Option liest einen festen fiktiven Wartungsdatensatz. Es sind keine realen Anlagen verbunden. Korrelation belegt keine Ursache.",
            )}
          </p>
          <p>
            <a href="/api/examples/inspection.csv" download>
              {t("Beispiel-CSV herunterladen")}
            </a>{" "}
            ·{" "}
            <a href="/api/examples/maintenance.pdf" download>
              {t("Beispiel-PDF herunterladen")}
            </a>
          </p>
        </Modal>
      )}
    </div>
  );
}

function Workspace({ id }: { id: string }) {
  useLanguage();
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
    t(
      "Welche Station hat sich zwischen Ausgangs- und Störungszeitraum am stärksten verändert? Nutze die hochgeladenen Belege, zitiere Quellen und trenne Beobachtungen von Hypothesen.",
    ),
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
          tr`${detail?.title || t("Untersuchung")} — Bericht`.slice(0, 120),
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
          ? t("Berichtsentwurf freigegeben und gespeichert.")
          : t("Vorschlag abgelehnt. Kein Entwurf gespeichert."),
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
        <p className="muted">{error || t("Fall wird geladen…")}</p>
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
          <p>{t("Daten zusammenführen. Belege nachvollziehen.")}</p>
        </div>
        <button
          className="primary"
          onClick={() => setAskOpen(true)}
          disabled={!sources.length || !!busy}
        >
          <Plus size={17} />
          {t("Neue Untersuchung")}
        </button>
      </div>
      {error && (
        <div className="banner error" role="alert">
          {t(error)}
          <button onClick={() => setError("")}>{t("Schließen")}</button>
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
          {t("Erstellt")}{" "}
          {new Date(detail.created_at).toLocaleDateString(getLocale(), {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </span>
        <span>
          <ShieldCheck size={14} />
          {t("Untersuchung mit rein lesendem Zugriff")}
        </span>
        <span>
          <BookOpen size={14} />
          {sources.length} {t("Belegquellen")}
        </span>
      </div>
      <div className="tabs-and-run">
        <div className="tabs" role="tablist" aria-label={t("Fallansichten")}>
          {[
            ["overview", LayoutDashboard, t("Übersicht")],
            ["activity", Activity, t("Aktivitäten")],
            ["report", FileText, t("Bericht")],
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
          <label htmlFor="run-select">{t("Untersuchung")}</label>
          <select
            id="run-select"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
          >
            <option value="">{t("Untersuchung auswählen")}</option>
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
                {t("Fortsetzen")}
                {tokenContinuation(run) ? t(" mit zusätzlicher Kapazität") : ""}
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
                  {t("Pausieren")}
                </button>
                <button
                  className="icon-button"
                  onClick={() => control("cancel")}
                  disabled={!!busy}
                  aria-label={t("Untersuchung abbrechen")}
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
                  {t("Fortsetzen")}
                </button>
                <button
                  className="secondary compact"
                  onClick={() => control("cancel")}
                  disabled={!!busy}
                >
                  {t("Abbrechen")}
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
                {t("Belegquellen")}
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
                {t("Verglichene Stationen")}
                <Table2 size={16} />
              </span>
              <strong>
                {comparison?.ranking.length.toString().padStart(2, "0") || "—"}
              </strong>
              <small>{t("Ausgangs- und Störungszeitraum")}</small>
            </div>
            <div className="stat">
              <span>
                {t("Größte Stationsabweichung")}
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
                  ? tr`${top.station_id} · beschreibender Befund`
                  : t("CSV zum Vergleichen hochladen")}
              </small>
            </div>
          </div>
          <div className="overview-grid">
            <div className="left-column">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>{t("Stationsleistung")}</h2>
                    <p>
                      {t("Fehlausschussquoten der Prüfstationen vergleichen.")}
                    </p>
                  </div>
                  <span className="subtle-tag">{t("CSV-ANALYSE")}</span>
                </div>
                {csvSources.length > 0 && (
                  <label className="source-select">
                    {t("Quelle")}
                    <select
                      aria-label={t("CSV-Quelle des Diagramms")}
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
                  <Empty title={chartError || t("Noch keine Stationsdaten")}>
                    {t(
                      "Prüf-CSV hochladen, um Quoten für Ausgangs- und Störungszeitraum zu berechnen.",
                    )}
                  </Empty>
                )}
              </section>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>{t("Dokumente durchsuchen")}</h2>
                    <p>
                      {t("Auszüge mit nachvollziehbaren Seitenangaben finden.")}
                    </p>
                  </div>
                  <BookOpen size={19} />
                </div>
                <form className="search-form" onSubmit={search}>
                  <Search size={17} />
                  <input
                    aria-label={t("Dokumentsuche")}
                    placeholder={t(
                      "Belege durchsuchen, z. B. Beleuchtung Belichtung…",
                    )}
                    value={query}
                    maxLength={500}
                    onChange={(e) => setQuery(e.target.value)}
                    required
                  />
                  <button
                    className="secondary compact"
                    disabled={!!busy || !query.trim()}
                  >
                    {t("Suchen")}
                  </button>
                </form>
                {hits === null ? (
                  <p className="hint">
                    {t(
                      "Durchsucht die PDFs dieses Falls nach Wörtern. Relevanz bedeutet keine sachliche Gewissheit.",
                    )}
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
                          <b>
                            {t("Seite")} {(h.pages || [h.page]).join(", ")}
                          </b>
                        </span>
                        <p>{h.text}</p>
                        <small>
                          {t("Quellenangabe prüfen")} <ArrowRight size={13} />
                        </small>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="hint">
                    {t(
                      "Keine passenden Auszüge. Ein leeres Ergebnis beweist nicht, dass etwas nicht vorhanden ist.",
                    )}
                  </p>
                )}
              </section>
            </div>
            <aside className="right-column">
              <section className="panel evidence-panel">
                <div className="panel-heading">
                  <h2>{t("Belegbibliothek")}</h2>
                  <span className="count">{sources.length}</span>
                </div>
                <div className="source-list">
                  {sources.map((s) => (
                    <SourceRow key={s.id} source={s} caseId={id} />
                  ))}
                  {!sources.length && (
                    <Empty title={t("Erste Quelle hinzufügen")}>
                      {t(
                        "Prüfdaten und unterstützende Dokumente zum Fall hinzufügen.",
                      )}
                    </Empty>
                  )}
                </div>
                <button
                  className="upload-button"
                  onClick={() => setUploadOpen(true)}
                >
                  <Upload size={16} />
                  {t("Belege hochladen")}
                </button>
                <p className="hint">
                  {t("PDF bis 10 MiB · CSV bis 2 MiB")}
                  <br />
                  {t("Nur synthetische oder lizenzierte öffentliche Daten.")}
                </p>
              </section>
              <section className="insight-card">
                <span className="eyebrow">
                  <ShieldCheck size={14} />
                  {t("BELEGE VOR SCHLUSSFOLGERUNGEN")}
                </span>
                <h3>{t("Ein Befund ist ein Ausgangspunkt.")}</h3>
                <p>
                  {t(
                    "Gleichzeitige Änderungen können eine Hypothese nahelegen. Sie beweisen keine Ursache. Prüfe Originalquellen und lege die nächste Prüfung fest.",
                  )}
                </p>
              </section>
              <div className="mock-note">
                <Wrench size={16} />
                <div>
                  <strong>{t("MCP-Testumgebung")}</strong>
                  <p>
                    {run?.use_mock_mcp
                      ? t(
                          "Simulation für die ausgewählte Untersuchung aktiviert.",
                        )
                      : t(
                          "Optionale lokale Simulation. Beim Start einer Untersuchung aktivieren.",
                        )}{" "}
                    {t("Keine realen Anlagen verbunden.")}
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
                {t("Modellaufrufe")}
              </span>
              <span>
                <b>
                  {run.tool_calls}/{run.limits.max_tool_calls}
                </b>{" "}
                {t("Werkzeugaufrufe")}
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
                {t("aktive Zeit")}
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
                {t("Ereignisverbindung:")} {streamError}
                {t(
                  ". Bei aktiver Untersuchung wird automatisch neu verbunden.",
                )}
              </p>
            )}
            <div className="activity-grid">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>{t("Untersuchungsverlauf")}</h2>
                    <p>
                      {t("Gespeicherte Ereignisse ·")} {events.length} recorded
                    </p>
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
                    <h2>{t("Ereignisdetails")}</h2>
                    <p>
                      {t(
                        "Werkzeugargumente und zurückgegebene Beobachtungen prüfen.",
                      )}
                    </p>
                  </div>
                  <Wrench size={18} />
                </div>
                {selectedEvent ? (
                  <>
                    <span className="subtle-tag">
                      {selectedEvent.type.replaceAll("_", " ")}
                    </span>
                    <p className="muted small">
                      {time(selectedEvent.at)} {t("· Ereignis")}{" "}
                      {selectedEvent.id}
                    </p>
                    {selectedEvent.data.tool_call_id && (
                      <>
                        <label>{t("Werkzeugaufruf")}</label>
                        <code className="break">
                          {String(selectedEvent.data.tool_call_id)}
                        </code>
                      </>
                    )}
                    {selectedEvent.type === "tool_finished" && (
                      <>
                        <label>{t("Argumente")}</label>
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
                        <label>{t("Beobachtung")}</label>
                      </>
                    )}
                    <Json
                      value={
                        selectedEvent.data.observation || selectedEvent.data
                      }
                    />
                  </>
                ) : (
                  <Empty title={t("Ereignis auswählen")}>
                    {t(
                      "Werkzeugaufruf öffnen, um Eingaben und Belege zu prüfen.",
                    )}
                  </Empty>
                )}
              </section>
            </div>
          </>
        ) : (
          <Empty title={t("Keine Untersuchung ausgewählt")}>
            {t(
              "Starte eine Untersuchung, um die Aktivitäten des Agenten zu sehen.",
            )}
          </Empty>
        ))}
      {tab === "report" && (
        <div className="report-grid">
          <section className="panel report-panel">
            <div className="panel-heading">
              <div>
                <h2>{t("Untersuchungsbericht")}</h2>
                <p>
                  {t("Modellbefunde · anhand der zitierten Belege prüfen.")}
                </p>
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
                  {t("JSON exportieren")}
                </button>
              )}
            </div>
            {report?.answer ? (
              <>
                <div className="report-answer">{report.answer}</div>
                <p className="notice">
                  {t(
                    "Korrelation belegt keine Ursache. Quellenprüfungen bestätigen Fundstellen, nicht die Richtigkeit einer Aussage.",
                  )}
                </p>
                <h3>{t("Quellenangaben")}</h3>
                {!report.citation_checks.has_answer_citations && (
                  <p className="notice">
                    {t(
                      "Die Antwort enthält keine erkannten Quellenangaben dieses Falls.",
                    )}
                  </p>
                )}
                {(report.citation_checks.unresolved.length > 0 ||
                  report.citation_checks.malformed.length > 0 ||
                  report.citation_checks.not_returned_by_tools.length > 0) && (
                  <details open className="notice">
                    <summary>{t("Quellenangaben prüfen")}</summary>
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
                            ? tr`Seite ${(c.pages || [c.page]).join(", ")}`
                            : tr`Zeile ${c.row?.row_id} · Zeile ${c.row?.csv_line}`}{" "}
                          ·{" "}
                          {c.cited_in_answer
                            ? t("In der Antwort zitiert")
                            : t("Vom Werkzeug zurückgegeben")}
                        </small>
                      </span>
                      <ChevronRight size={15} />
                    </button>
                  ))}
                </div>
                <details className="method">
                  <summary>{t("Unsicherheit und Einschränkungen")}</summary>
                  <ul>
                    {report.uncertainty.limitations.map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                  </ul>
                </details>
              </>
            ) : (
              <Empty
                title={
                  active ? t("Untersuchung läuft") : t("Noch keine Befunde")
                }
              >
                {active
                  ? t(
                      "Prüfe den Fortschritt unter Aktivitäten. Befunde erscheinen hier, sobald die Untersuchung endet.",
                    )
                  : t(
                      "Schließe eine Untersuchung ab, um ihre Befunde zu prüfen und zu exportieren.",
                    )}
              </Empty>
            )}
          </section>
          <section className="panel draft-panel">
            <div className="panel-heading">
              <div>
                <h2>{t("Berichtsentwurf")}</h2>
                <p>{t("Prüfen, bearbeiten und Speichern freigeben.")}</p>
              </div>
              <FilePlus2 size={19} />
            </div>
            {run?.status === "completed" && report?.answer ? (
              <>
                <label htmlFor="draft-title">{t("Titel")}</label>
                <input
                  id="draft-title"
                  maxLength={120}
                  value={draftTitle}
                  onChange={(e) => setDraftTitle(e.target.value)}
                />
                <label htmlFor="draft-body">{t("Entwurfstext")}</label>
                <textarea
                  id="draft-body"
                  rows={16}
                  maxLength={20000}
                  value={draftBody}
                  onChange={(e) => setDraftBody(e.target.value)}
                />
                <p className="hint">
                  {t(
                    "Änderungen bleiben bis zur Prüfanforderung in diesem Browser. Eine separate Freigabe speichert exakt den Inhalt der Vorschau.",
                  )}
                </p>
                <button
                  className="primary full"
                  onClick={() => void previewDraft()}
                  disabled={!!busy || !draftBody.trim() || !draftTitle.trim()}
                >
                  <ShieldCheck size={16} />
                  {t("Entwurf zur Freigabe prüfen")}
                </button>
              </>
            ) : (
              <p className="muted">
                {t(
                  "Für einen Entwurf ist eine abgeschlossene Untersuchung erforderlich.",
                )}
              </p>
            )}
            {proposals.filter((p) => p.status === "pending").length > 0 && (
              <div className="saved-drafts">
                <h3>{t("Ausstehende Freigaben")}</h3>
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
                        <small>{t("Wartet auf deine Prüfung")}</small>
                      </span>
                      <ChevronRight size={15} />
                    </button>
                  ))}
              </div>
            )}
            {drafts.length > 0 && (
              <div className="saved-drafts">
                <h3>{t("Freigegebene Entwürfe")}</h3>
                {drafts.map((d) => (
                  <button
                    className="saved-draft"
                    key={d.id}
                    onClick={() =>
                      download(
                        `eil-draft-${d.id.slice(0, 8)}.md`,
                        tr`# ${d.title}\n\n${d.body}

---
Untersuchung: ${d.run_id}
Freigegebener Vorschlag: ${d.proposal_id}
SHA-256 des Inhalts: ${d.sha256}

Experimentelle Befunde; Belege prüfen. Korrelation belegt keine Ursache.

`,
                        "text/markdown",
                      )
                    }
                  >
                    <Check size={15} />
                    <span>
                      {d.title}
                      <small>{t("Freigegeben · Markdown herunterladen")}</small>
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
        <span>
          {t(
            "Lokale Forschung · Synthetische Belege · Menschliche Beurteilung",
          )}
        </span>
      </footer>
      {uploadOpen && (
        <UploadModal
          id={id}
          onClose={() => setUploadOpen(false)}
          onDone={() => {
            setUploadOpen(false);
            setRevision((x) => x + 1);
            setMessage(
              t("Belege hochgeladen und für neue Untersuchungen verfügbar."),
            );
          }}
        />
      )}
      {askOpen && (
        <Modal
          title={t("Untersuchung starten")}
          onClose={() => setAskOpen(false)}
        >
          <form onSubmit={start}>
            <label htmlFor="question">{t("Untersuchungsfrage")}</label>
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
              {t("Diese Untersuchung nutzt einen festen Stand der")}{" "}
              {sources.length} {t("aktuellen Belegquelle(n).")}
            </p>
            <label htmlFor="timeout">
              {t("Aktives Zeitbudget (Sekunden)")}
            </label>
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
              {t(
                "8 Modellaufrufe · 16 Werkzeugaufrufe · 32.768 Token · 35 Schritte. Budgets bleiben beim Pausieren und Fortsetzen erhalten.",
              )}
            </p>
            <label htmlFor="output-tokens">
              {t("Maximale Ausgabetoken pro Modellaufruf")}
            </label>
            <select
              id="output-tokens"
              value={outputTokens}
              onChange={(e) => setOutputTokens(Number(e.target.value))}
            >
              <option value={1024}>1,024 (default)</option>
              <option value={2048}>
                {t("2.048 (längere Überlegungen / Antworten)")}
              </option>
            </select>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={useMcp}
                onChange={(e) => setUseMcp(e.target.checked)}
              />
              <span>
                {t("Rein lesenden MCP-Simulationskontext erlauben")}
                <small>
                  {t(
                    "Fester lokaler synthetischer Wartungsserver. Keine Falldateien werden übertragen. Diese Untersuchung kann fiktive Stationsnotizen lesen.",
                  )}
                </small>
              </span>
            </label>
            {error && (
              <p className="error-text" role="alert">
                {t(error)}
              </p>
            )}
            <div className="modal-actions">
              <button
                className="secondary"
                type="button"
                onClick={() => setAskOpen(false)}
              >
                {t("Abbrechen")}
              </button>
              <button className="primary" disabled={!!busy || !question.trim()}>
                <Play size={15} />
                {busy === "start"
                  ? t("Wird gestartet…")
                  : t("Untersuchung starten")}
              </button>
            </div>
          </form>
        </Modal>
      )}
      {citation && (
        <Modal
          title={t("Belegreferenz")}
          onClose={() => setCitation(null)}
          wide
        >
          <CitationView citation={citation} />
        </Modal>
      )}
      {proposal && (
        <Modal
          title={t("Berichtsentwurf freigeben")}
          onClose={() => setProposal(null)}
          wide
        >
          <div className="approval-notice">
            <ShieldCheck size={20} />
            <div>
              <strong>
                {t("Diese Aktion speichert einen Berichtsentwurf.")}
              </strong>
              <p>
                {t(
                  "Prüfe den vollständigen Inhalt unten. Die Freigabe speichert exakt diese Version im Fall. Sie bestätigt nicht die Richtigkeit der Aussagen.",
                )}
              </p>
            </div>
          </div>
          <h3>{proposal.title}</h3>
          <div className="approval-preview">{proposal.body}</div>
          <label>{t("SHA-256 des Inhalts")}</label>
          <code className="break">{proposal.sha256}</code>
          {error && (
            <p className="error-text" role="alert">
              {t(error)}
            </p>
          )}
          <div className="modal-actions">
            <button
              className="secondary"
              onClick={() => void decide("reject")}
              disabled={!!busy}
            >
              {t("Vorschlag ablehnen")}
            </button>
            <button
              className="primary"
              onClick={() => void decide("approve")}
              disabled={!!busy}
            >
              <Check size={16} />
              {busy === "decision"
                ? t("Wird gespeichert…")
                : t("Entwurf freigeben und speichern")}
            </button>
          </div>
        </Modal>
      )}
    </main>
  );
}

function SourceRow({ source, caseId }: { source: Source; caseId: string }) {
  useLanguage();
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
              ? tr`${fmt(source.row_count)} Zeilen`
              : tr`${source.page_count} Seiten`}
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
          {t("Original herunterladen")}
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
  useLanguage();
  const [file, setFile] = useState<File | null>(null),
    [policy, setPolicy] = useState("synthetic"),
    [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    if (!/\.(pdf|csv)$/i.test(file.name)) {
      setError(t("PDF- oder CSV-Datei auswählen."));
      return;
    }
    const max = /\.pdf$/i.test(file.name) ? 10 : 2;
    if (file.size > max * 1024 * 1024) {
      setError(tr`Diese Datei überschreitet die Grenze von ${max} MiB.`);
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
    <Modal title={t("Belege hochladen")} onClose={onClose}>
      <form onSubmit={upload}>
        <p className="muted">
          {t(
            "Quellen sind unveränderlich und auf diesen Fall beschränkt. Neue Uploads stehen neuen Untersuchungen zur Verfügung.",
          )}
        </p>
        <label className="file-drop" htmlFor="evidence-file">
          <Upload size={25} />
          <strong>{file?.name || t("PDF oder CSV auswählen")}</strong>
          <span>{t("PDF bis 10 MiB / 20 Seiten · CSV bis 2 MiB")}</span>
          <input
            id="evidence-file"
            type="file"
            accept=".csv,.pdf"
            required
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
        <label htmlFor="data-policy">{t("Datenkategorie")}</label>
        <select
          id="data-policy"
          value={policy}
          onChange={(e) => setPolicy(e.target.value)}
        >
          <option value="synthetic">
            {t("Synthetische / generierte Demodaten")}
          </option>
          <option value="licensed-public">
            {t("Ausdrücklich lizenzierte öffentliche Daten")}
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
            {t(
              "Ich bestätige, dass diese Datei zur gewählten Datenkategorie gehört und keine internen oder sensiblen Informationen enthält.",
            )}
          </span>
        </label>
        <p className="hint">
          {t(
            "PDF-Konvertierung erfolgt lokal ohne OCR. Gescannte PDFs enthalten möglicherweise keinen extrahierbaren Text.",
          )}
        </p>
        <p className="hint">
          <a href="/api/examples/inspection.csv" download>
            {t("Beispiel-CSV")}
          </a>{" "}
          ·{" "}
          <a href="/api/examples/maintenance.pdf" download>
            {t("Beispiel-PDF")}
          </a>
        </p>
        {error && (
          <p className="error-text" role="alert">
            {t(error)}
          </p>
        )}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>
            {t("Abbrechen")}
          </button>
          <button className="primary" disabled={busy || !file || !confirmed}>
            {busy ? (
              <>
                <LoaderCircle className="spin" size={16} />
                {t("Lokale Verarbeitung…")}
              </>
            ) : (
              <>
                <Upload size={16} />
                {t("Belege hochladen")}
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
