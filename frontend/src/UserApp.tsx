import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  Beaker,
  Check,
  ChevronRight,
  FileText,
  LockKeyhole,
  LoaderCircle,
  Paperclip,
  Plus,
  Table2,
  X,
} from "lucide-react";
import { api } from "./api";
import {
  friendlyStatus,
  fromSource,
  startUserInvestigation,
  validateFiles,
  type Attachment,
} from "./userFlow";
import type { Case, CaseDetail, Run } from "./types";
import UserResults from "./UserResults";
import "./user.css";

type Route = { page: string; caseId: string; runId: string };
const readRoute = (): Route => {
  const p = new URLSearchParams(location.search);
  return {
    page: p.get("page") || "new",
    caseId: p.get("case") || "",
    runId: p.get("run") || "",
  };
};
function url(route: Route) {
  const p = new URLSearchParams();
  if (route.page !== "new") p.set("page", route.page);
  if (route.caseId) p.set("case", route.caseId);
  if (route.runId) p.set("run", route.runId);
  return p.size ? `/?${p}` : "/";
}
export function advancedUrl(caseId = "", runId = "") {
  const p = new URLSearchParams({ view: "advanced" });
  if (caseId) p.set("case", caseId);
  if (runId) p.set("run", runId);
  return `/?${p}`;
}
export const message = (error: unknown) =>
  error instanceof Error ? error.message : String(error);

export default function UserApp() {
  const [route, setRoute] = useState(readRoute),
    [navigation, setNavigation] = useState(0);
  const [cases, setCases] = useState<Case[]>([]),
    [runs, setRuns] = useState<Run[]>([]);
  const [detail, setDetail] = useState<CaseDetail | null>(null),
    [error, setError] = useState("");
  const [revision, setRevision] = useState(0),
    [busy, setBusy] = useState(false);
  function navigate(next: Route, force = false) {
    if (busy && !force) return;
    history.pushState(null, "", url(next));
    setRoute(next);
    setNavigation((n) => n + 1);
    window.scrollTo(0, 0);
  }
  useEffect(() => {
    const onPop = () => {
      setRoute(readRoute());
      setNavigation((n) => n + 1);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    void Promise.all([
      api<{ cases: Case[] }>("/api/cases", { signal: controller.signal }),
      api<{ investigations: Run[] }>("/api/investigations", {
        signal: controller.signal,
      }),
    ])
      .then(([c, r]) => {
        setCases(c.cases);
        setRuns(r.investigations.filter((x) => x.case_id));
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(message(e));
      });
    return () => controller.abort();
  }, [route.page, route.runId, revision]);
  useEffect(() => {
    setDetail(null);
    if (!route.caseId) return;
    const controller = new AbortController();
    void api<CaseDetail>(`/api/cases/${route.caseId}`, {
      signal: controller.signal,
    })
      .then(setDetail)
      .catch((e) => {
        if (!controller.signal.aborted) setError(message(e));
      });
    return () => controller.abort();
  }, [route.caseId, navigation]);
  const home = () => navigate({ page: "new", caseId: "", runId: "" });
  const selectedDetail = detail?.id === route.caseId ? detail : null;
  const open = (c: Case) => {
    const r = runs.find((x) => x.case_id === c.id);
    navigate({ page: "new", caseId: c.id, runId: r?.id || "" });
  };
  return (
    <div className="user-app">
      <header className="ux-header">
        <button className="ux-brand" onClick={home} disabled={busy}>
          <Beaker size={29} />
          <span>Engineering Intelligence Lab</span>
        </button>
        <nav aria-label="Main navigation">
          <a href="/?page=siemens">SPS help</a>
          <button
            onClick={() =>
              navigate({ page: "investigations", caseId: "", runId: "" })
            }
            disabled={busy}
          >
            My investigations
          </button>
          <span className="ux-avatar" aria-label="Local workspace">
            L
          </span>
        </nav>
      </header>
      <main className={route.runId ? "ux-main ux-results" : "ux-main"}>
        {error && (
          <div className="ux-error" role="alert">
            {error}
            <button onClick={() => setRevision((n) => n + 1)}>Try again</button>
          </div>
        )}
        {route.runId ? (
          <UserResults
            key={route.runId}
            id={route.runId}
            caseId={route.caseId}
            detail={selectedDetail}
            onBack={() =>
              navigate({ page: "investigations", caseId: "", runId: "" })
            }
            onAnother={() =>
              navigate({ page: "new", caseId: route.caseId, runId: "" })
            }
          />
        ) : route.page === "investigations" ? (
          <>
            <div className="ux-list-heading">
              <div>
                <h1>My investigations</h1>
                <p>Your files, questions, and findings in one place.</p>
              </div>
              <button className="ux-primary" onClick={home}>
                <Plus size={17} />
                New investigation
              </button>
            </div>
            <Recent cases={cases} runs={runs} onOpen={open} />
          </>
        ) : (
          <>
            {route.caseId && !selectedDetail ? (
              <p className="ux-loading">
                {error
                  ? "This investigation could not be opened."
                  : "Opening your files…"}
              </p>
            ) : (
              <QuestionForm
                key={`${route.caseId}:${navigation}`}
                existing={selectedDetail}
                onBusy={setBusy}
                onCase={(id) => {
                  history.replaceState(
                    null,
                    "",
                    url({ page: "new", caseId: id, runId: "" }),
                  );
                  setRevision((n) => n + 1);
                }}
                onStarted={(r) =>
                  navigate(
                    { page: "new", caseId: r.case_id, runId: r.id },
                    true,
                  )
                }
              />
            )}
            <section className="ux-recent" aria-labelledby="recent-title">
              <div>
                <h2 id="recent-title">Recent investigations</h2>
                {cases.length > 3 && (
                  <button
                    className="ux-link"
                    onClick={() =>
                      navigate({
                        page: "investigations",
                        caseId: "",
                        runId: "",
                      })
                    }
                  >
                    View all
                    <ArrowRight size={14} />
                  </button>
                )}
              </div>
              <Recent cases={cases.slice(0, 3)} runs={runs} onOpen={open} />
            </section>
          </>
        )}
        <footer className="ux-footer">
          <a
            href={advancedUrl(
              new URLSearchParams(location.search).get("case") || "",
              route.runId,
            )}
          >
            Advanced workspace
          </a>
        </footer>
      </main>
    </div>
  );
}

function Recent({
  cases,
  runs,
  onOpen,
}: {
  cases: Case[];
  runs: Run[];
  onOpen: (c: Case) => void;
}) {
  return (
    <div className="ux-recent-list">
      {cases.length ? (
        cases.map((c) => {
          const run = runs.find((r) => r.case_id === c.id);
          return (
            <button key={c.id} onClick={() => onOpen(c)}>
              <span>{c.title}</span>
              <small>
                {run ? friendlyStatus(run.status) : "Files ready"} ·{" "}
                {new Date(c.created_at).toLocaleDateString([], {
                  month: "short",
                  day: "numeric",
                })}
              </small>
              <ChevronRight size={17} />
            </button>
          );
        })
      ) : (
        <div className="ux-no-history">
          Your investigations will appear here.
        </div>
      )}
    </div>
  );
}

function QuestionForm({
  existing,
  onBusy,
  onCase,
  onStarted,
}: {
  existing: CaseDetail | null;
  onBusy: (b: boolean) => void;
  onCase: (id: string) => void;
  onStarted: (r: Run) => void;
}) {
  const [question, setQuestion] = useState(""),
    [files, setFiles] = useState<Attachment[]>(
      existing?.sources.map(fromSource) || [],
    );
  const [caseId, setCaseId] = useState(existing?.id || ""),
    [policy, setPolicy] = useState("synthetic");
  const [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(""),
    [error, setError] = useState("");
  const hasNewFiles = files.some((f) => !f.source);
  function add(incoming: File[]) {
    try {
      validateFiles(files, incoming);
      setFiles((previous) => [
        ...previous,
        ...incoming.map((file) => ({
          key: crypto.randomUUID(),
          name: file.name,
          size: file.size,
          file,
        })),
      ]);
      setConfirmed(false);
      setError("");
    } catch (e) {
      setError(message(e));
    }
  }
  async function example() {
    setBusy(true);
    onBusy(true);
    setError("");
    setProgress("Loading demo files…");
    try {
      const generated = await Promise.all(
        [
          ["inspection.csv", "inspection_data.csv"],
          ["maintenance.pdf", "maintenance_note.pdf"],
        ].map(async ([endpoint, name]) => {
          const r = await fetch(`/api/examples/${endpoint}`);
          if (!r.ok)
            throw new Error(
              "The demo files are unavailable. Try uploading your own files.",
            );
          return new File([await r.blob()], name);
        }),
      );
      add(generated);
      setPolicy("synthetic");
      setConfirmed(true);
      setQuestion("Why did false rejects increase at station S03?");
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
      onBusy(false);
      setProgress("");
    }
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!question.trim() || !files.length || (hasNewFiles && !confirmed))
      return;
    setBusy(true);
    onBusy(true);
    setError("");
    try {
      const run = await startUserInvestigation({
        question,
        files,
        caseId,
        policy,
        onCase: (id) => {
          setCaseId(id);
          onCase(id);
        },
        onProgress: setProgress,
        onUploaded: (key, source) =>
          setFiles((previous) =>
            previous.map((f) =>
              f.key === key ? { ...f, name: source.filename, source } : f,
            ),
          ),
      });
      onBusy(false);
      onStarted(run);
    } catch (e) {
      setError(
        `${message(e)} Any successfully uploaded files are kept. You can retry.`,
      );
    } finally {
      setBusy(false);
      onBusy(false);
      setProgress("");
    }
  }
  return (
    <>
      <div className="ux-steps" aria-label="Investigation steps">
        <span className="current">
          <b>1</b>Add files
        </span>
        <i />
        <span>
          <b>2</b>Ask a question
        </span>
        <i />
        <span>
          <b>3</b>Review findings
        </span>
      </div>
      <div className="ux-intro">
        <h1>What would you like to investigate?</h1>
        <p>
          {existing
            ? "Ask another question using these files, or add more evidence."
            : "Add your files and ask in plain language."}
        </p>
      </div>
      <form className="ux-question-card" onSubmit={submit}>
        <label htmlFor="user-question">Your question</label>
        <textarea
          id="user-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Why did false rejects increase at station S03?"
          maxLength={4000}
          required
          rows={3}
          disabled={busy}
        />
        <label
          className={`ux-add-files ${busy ? "disabled" : ""}`}
          htmlFor="user-files"
        >
          <Paperclip size={23} />
          <span>Add CSV or PDF files</span>
          <input
            id="user-files"
            type="file"
            accept=".csv,.pdf"
            multiple
            disabled={busy}
            onChange={(e) => {
              add(Array.from(e.target.files || []));
              e.target.value = "";
            }}
          />
        </label>
        <div className="ux-attachments">
          {files.map((f) => (
            <div key={f.key}>
              {/\.csv$/i.test(f.name) ? (
                <Table2 className="ux-csv" size={21} />
              ) : (
                <FileText size={21} />
              )}
              <span>{f.name}</span>
              {f.source ? (
                <Check size={18} aria-label="File ready" className="ux-ready" />
              ) : (
                <button
                  type="button"
                  aria-label={`Remove ${f.name}`}
                  disabled={busy}
                  onClick={() =>
                    setFiles((prev) => prev.filter((x) => x.key !== f.key))
                  }
                >
                  <X size={16} />
                </button>
              )}
            </div>
          ))}
        </div>
        {hasNewFiles && (
          <div className="ux-data-policy">
            <label htmlFor="user-data-policy">File category</label>
            <select
              id="user-data-policy"
              value={policy}
              disabled={busy}
              onChange={(e) => {
                setPolicy(e.target.value);
                setConfirmed(false);
              }}
            >
              <option value="synthetic">Synthetic / generated data</option>
              <option value="licensed-public">Licensed public data</option>
            </select>
            <label className="ux-confirm">
              <input
                type="checkbox"
                required
                checked={confirmed}
                disabled={busy}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              <span>
                I confirm these files match this category and contain no
                internal or sensitive information.
              </span>
            </label>
          </div>
        )}
        {error && (
          <p className="ux-error" role="alert">
            {error}
          </p>
        )}
        {busy && (
          <p className="ux-preparing" role="status">
            <LoaderCircle className="spin" size={17} />
            {progress}
          </p>
        )}
        <div className="ux-form-bottom">
          <div>
            <span>Synthetic or licensed public data only.</span>
            {!files.length && (
              <button
                type="button"
                className="ux-link"
                disabled={busy}
                onClick={() => void example()}
              >
                Try the demo files
              </button>
            )}
          </div>
          <button
            className="ux-primary"
            disabled={
              busy ||
              !question.trim() ||
              !files.length ||
              (hasNewFiles && !confirmed)
            }
          >
            {busy ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <>
                Investigate
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </div>
      </form>
      <p className="ux-local">
        <LockKeyhole size={15} />
        Your files are processed locally.
      </p>
    </>
  );
}
