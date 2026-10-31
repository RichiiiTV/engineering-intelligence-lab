import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post } from "./api";
import type { Source } from "./MachineApp";
import type { EvidenceReport, Run } from "./types";
import { friendlyStatus } from "./userFlow";
import { stopped } from "./useInvestigation";
import SafeAnswer from "./SafeAnswer";
import { LibraryReferences } from "./KnowledgeLibrary";
import SiemensReferences from "./SiemensReferences";

type Notebook = {
  id: string;
  title: string;
  document_ids: string[];
  library_document_ids: string[];
  revision: number;
  turns?: Run[];
};
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function NotebookPanel({
  machineId,
  sources,
}: {
  machineId: string;
  sources: Source[];
}) {
  const base = "/api/machines/" + machineId + "/notebooks";
  const [rows, setRows] = useState<Notebook[]>([]),
    [selected, setSelected] = useState(
      new URLSearchParams(location.search).get("notebook") || "",
    );
  const [notebook, setNotebook] = useState<Notebook | null>(null),
    [question, setQuestion] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [publicEnabled, setPublicEnabled] = useState(false),
    [publicQuestion, setPublicQuestion] = useState("");
  const [loadError, setLoadError] = useState("");
  const submission = useRef<{ body: string; id: string } | null>(null);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  async function refresh() {
    try {
      setRows((await api<{ notebooks: Notebook[] }>(base)).notebooks);
      if (selected) {
        const result = await api<Notebook>(base + "/" + selected);
        if (selectedRef.current === selected) setNotebook(result);
      }
      setLoadError("");
    } catch (e) {
      setLoadError(msg(e));
    }
  }
  useEffect(() => {
    setNotebook(null);
    setError("");
    void refresh();
    const timer = setInterval(() => void refresh(), 1800);
    return () => clearInterval(timer);
  }, [selected, machineId]);
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
      return true;
    } catch (e) {
      setError(msg(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  function select(id: string) {
    setSelected(id);
    setQuestion("");
    setPublicQuestion("");
    setPublicEnabled(false);
    submission.current = null;
    const url = new URL(location.href);
    if (id) url.searchParams.set("notebook", id);
    else url.searchParams.delete("notebook");
    history.replaceState(null, "", url);
  }
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    await action(async () => {
      const n = await post<Notebook>(base, {
        title: new FormData(form).get("title"),
        document_ids: sources.filter((s) => s.active).map((s) => s.id),
      });
      select(n.id);
    });
  }
  async function ask(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const content = {
      question: question.trim(),
      ...(publicEnabled
        ? { siemens: { question: publicQuestion.trim() } }
        : {}),
    };
    const body = JSON.stringify(content);
    if (submission.current?.body !== body)
      submission.current = { body, id: crypto.randomUUID() };
    const ok = await action(() =>
      post(base + "/" + selected + "/questions", {
        ...content,
        request_id: submission.current!.id,
      }),
    );
    if (ok) {
      setQuestion("");
      setPublicQuestion("");
      setPublicEnabled(false);
      submission.current = null;
    }
  }
  const active = notebook?.turns?.some(
    (r) => r.status === "queued" || r.status === "running",
  );
  const activeSources = sources.filter((s) => s.active),
    available = new Set(activeSources.map((s) => s.id));
  const changed =
    notebook &&
    (activeSources.some((s) => !notebook.document_ids.includes(s.id)) ||
      notebook.document_ids.some((id) => !available.has(id)));
  return (
    <section className="machine-card notebook-panel">
      <div className="ux-list-heading">
        <h2>Notizbücher</h2>
        {selected && (
          <button onClick={() => select("")}>Alle Notizbücher</button>
        )}
      </div>
      {(error || loadError) && (
        <p className="ux-error" role="alert">
          {error || loadError}
        </p>
      )}
      {!selected ? (
        <>
          <p>
            Zusammengehörige Fragen bündeln. Jedes Notizbuch behält seine
            ausgewählten Quellen und den jüngsten Gesprächsverlauf.
          </p>
          {rows.map((n) => (
            <button
              className="machine-link"
              key={n.id}
              onClick={() => select(n.id)}
            >
              <span>
                <strong>{n.title}</strong>
                <small>
                  {n.document_ids.length} Maschinenquellen · Auswahl{" "}
                  {n.revision}
                </small>
              </span>
              <span>Öffnen →</span>
            </button>
          ))}
          <form className="machine-form" onSubmit={create}>
            <label>
              Neues Notizbuch
              <input
                name="title"
                required
                maxLength={120}
                placeholder="z. B. Unerwartete Förderbandstopps"
              />
            </label>
            <button className="ux-primary" disabled={busy}>
              Notizbuch erstellen
            </button>
            <small>
              Beginnt mit den aktuell verfügbaren Maschinenquellen. Du kannst
              die Auswahl vor einer Frage ändern.
            </small>
          </form>
        </>
      ) : !notebook ? (
        <p>Notizbuch wird geöffnet…</p>
      ) : (
        <>
          <h3>{notebook.title}</h3>
          {changed && (
            <p className="ux-caution">
              Die verfügbaren Quellen haben sich geändert. Prüfe die Auswahl
              unten; vorherige Antworten behalten ihre ursprünglichen Quellen.
            </p>
          )}
          <details className="notebook-selection">
            <summary>
              {notebook.document_ids.length} Maschinenquellen ausgewählt ·
              Revision {notebook.revision}
            </summary>
            <form
              className="machine-form"
              key={notebook.id + ":" + notebook.revision}
              onSubmit={(e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                void action(() =>
                  post(base + "/" + selected + "/sources", {
                    document_ids: data.getAll("document"),
                    library_document_ids: [],
                  }),
                );
              }}
            >
              {activeSources.map((s) => (
                <label className="machine-check" key={s.id}>
                  <input
                    name="document"
                    type="checkbox"
                    value={s.id}
                    defaultChecked={notebook.document_ids.includes(s.id)}
                  />
                  {s.title} · {s.version}
                </label>
              ))}
              <button className="ux-secondary" disabled={busy || active}>
                Auswahl für nächste Antwort speichern
              </button>
            </form>
          </details>
          <div className="notebook-turns">
            {notebook.turns?.map((r) => (
              <NotebookTurn
                key={r.id}
                run={r}
                onCancel={() =>
                  action(() => post("/api/investigations/" + r.id + "/cancel"))
                }
              />
            ))}
          </div>
          <form className="machine-form notebook-composer" onSubmit={ask}>
            <label>
              {notebook.turns?.length
                ? "Rückfrage stellen"
                : "Frage zu dieser Maschine stellen"}
              <textarea
                rows={4}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                required
                maxLength={4000}
                placeholder="Was könnte den Stopp erklären, und welche Code- oder Handbuchstelle stützt diese Vermutung?"
              />
            </label>
            <details>
              <summary>
                Öffentliche Siemens-Dokumentation prüfen (optional)
              </summary>
              <p className="ux-small">
                Nur die hier separat eingegebene öffentliche Frage wird an
                Siemens gesendet. Keine internen Maschinennamen, Quelltexte oder
                Code in dieses Feld eintragen.
              </p>
              <label className="machine-check">
                <input
                  type="checkbox"
                  checked={publicEnabled}
                  onChange={(e) => setPublicEnabled(e.target.checked)}
                />
                Diese öffentliche Frage für diese Antwort verwenden
              </label>
              {publicEnabled && (
                <label>
                  Öffentliche Siemens-Frage
                  <textarea
                    rows={2}
                    value={publicQuestion}
                    onChange={(e) => setPublicQuestion(e.target.value)}
                    required
                    maxLength={500}
                  />
                </label>
              )}
            </details>
            <button
              className="ux-primary"
              disabled={
                busy ||
                active ||
                !question.trim() ||
                !!notebook.document_ids.some((id) => !available.has(id))
              }
            >
              {active
                ? "Untersuchung läuft…"
                : busy
                  ? "Wird gestartet…"
                  : "Frage stellen →"}
            </button>
            <small>
              Lokales Modell · Rein lesende Werkzeuge · Letzte vier
              abgeschlossene Gespräche im begrenzten Kontext
            </small>
          </form>
        </>
      )}
    </section>
  );
}

function NotebookTurn({
  run,
  onCancel,
}: {
  run: Run;
  onCancel: () => Promise<boolean>;
}) {
  const [report, setReport] = useState<EvidenceReport | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    if (!stopped.has(run.status)) return;
    const c = new AbortController();
    void api<EvidenceReport>("/api/investigations/" + run.id + "/export", {
      signal: c.signal,
    })
      .then(setReport)
      .catch((e) => {
        if (!c.signal.aborted) setError(msg(e));
      });
    return () => c.abort();
  }, [run.id, run.status]);
  return (
    <article className="notebook-turn">
      <div className="notebook-question">{run.question}</div>
      <p className="ux-small">
        {friendlyStatus(run.status)} ·{" "}
        <a href={`/?run=${run.id}`}>Details und Steuerung der Untersuchung</a>
      </p>
      {!stopped.has(run.status) && (
        <button onClick={() => void onCancel()}>Abbrechen</button>
      )}
      {error && <p role="alert">{error}</p>}
      {report && (
        <>
          <p
            className={
              report.answer_contract?.outcome === "needs_review"
                ? "ux-caution"
                : "ux-small"
            }
          >
            {report.answer_contract?.outcome === "needs_review"
              ? "Prüfung erforderlich"
              : report.answer_contract?.outcome === "no_support"
                ? "Die ausgewählten Quellen belegen keine Antwort"
                : report.answer_contract?.outcome === "budget_limited"
                  ? "Teilweise Belegprüfung"
                  : "Quellenverweise geprüft; technische Aussagen müssen geprüft werden"}
          </p>
          {report.answer_contract?.issues.map((issue) => (
            <p className="ux-caution" key={issue}>
              {issue}
            </p>
          ))}
          <SafeAnswer
            text={report.answer || "Keine abschließende Antwort erhalten."}
            references={report.library_citations}
            prefix={run.id + "-"}
          />
          <LibraryReferences
            report={report}
            runId={run.id}
            prefix={run.id + "-"}
          />
          <SiemensReferences report={report} />
        </>
      )}
    </article>
  );
}
