import { useLanguage, t, getLocale, tr } from "./i18n";
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
import { isSiemensQuestion } from "./siemens";
import { LibraryChooser, type LibrarySelection } from "./KnowledgeLibrary";
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
  useLanguage();
  const [route, setRoute] = useState(readRoute),
    [navigation, setNavigation] = useState(0);
  const [cases, setCases] = useState<Case[]>([]),
    [runs, setRuns] = useState<Run[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [nextRunOffset, setNextRunOffset] = useState<number | null>(null);
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
      api<{ cases: Case[]; next_offset?: number | null }>("/api/cases", {
        signal: controller.signal,
      }),
      api<{ investigations: Run[]; next_offset?: number | null }>(
        "/api/investigations",
        {
          signal: controller.signal,
        },
      ),
    ])
      .then(([c, r]) => {
        setCases(c.cases);
        setNextOffset(c.next_offset ?? null);
        setRuns(r.investigations);
        setNextRunOffset(r.next_offset ?? null);
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
  const open = async (c: Case) => {
    setBusy(true);
    try {
      const data = await api<{ investigations: Run[] }>(
        `/api/investigations?case_id=${c.id}&limit=1`,
      );
      navigate(
        { page: "new", caseId: c.id, runId: data.investigations[0]?.id || "" },
        true,
      );
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  async function loadMore() {
    if ((nextOffset === null && nextRunOffset === null) || busy) return;
    setBusy(true);
    try {
      const [page, history] = await Promise.all([
        nextOffset === null
          ? Promise.resolve(null)
          : api<{ cases: Case[]; next_offset: number | null }>(
              `/api/cases?offset=${nextOffset}&limit=50`,
            ),
        nextRunOffset === null
          ? Promise.resolve(null)
          : api<{ investigations: Run[]; next_offset: number | null }>(
              `/api/investigations?offset=${nextRunOffset}&limit=50`,
            ),
      ]);
      if (page) {
        setCases((old) => [
          ...new Map([...old, ...page.cases].map((c) => [c.id, c])).values(),
        ]);
        setNextOffset(page.next_offset);
      }
      if (history) {
        setRuns((old) => [
          ...new Map(
            [...old, ...history.investigations].map((r) => [r.id, r]),
          ).values(),
        ]);
        setNextRunOffset(history.next_offset);
      }
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="user-app">
      <header className="ux-header">
        <button className="ux-brand" onClick={home} disabled={busy}>
          <Beaker size={29} />
          <span>Engineering Intelligence Lab</span>
        </button>
        <nav aria-label={t("Hauptnavigation")}>
          <a href="/?page=machines">{t("Meine Maschinen")}</a>
          <button
            onClick={() =>
              navigate({ page: "investigations", caseId: "", runId: "" })
            }
            disabled={busy}
          >
            {t("Meine Untersuchungen")}
          </button>
          <span className="ux-avatar" aria-label={t("Lokaler Arbeitsbereich")}>
            L
          </span>
        </nav>
      </header>
      <main className={route.runId ? "ux-main ux-results" : "ux-main"}>
        {error && (
          <div className="ux-error" role="alert">
            {t(error)}
            <button onClick={() => setRevision((n) => n + 1)}>
              {t("Erneut versuchen")}
            </button>
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
                <h1>{t("Meine Untersuchungen")}</h1>
                <p>{t("Dateien, Fragen und Befunde an einem Ort.")}</p>
              </div>
              <button className="ux-primary" onClick={home}>
                <Plus size={17} />
                {t("Neue Untersuchung")}
              </button>
            </div>
            <Recent
              cases={cases}
              runs={runs}
              onOpen={open}
              onQuestion={(r) =>
                navigate({ page: "new", caseId: "", runId: r.id })
              }
            />
            {(nextOffset !== null || nextRunOffset !== null) && (
              <button
                className="ux-secondary"
                disabled={busy}
                onClick={() => void loadMore()}
              >
                {busy ? t("Wird geladen…") : t("Weitere Untersuchungen laden")}
              </button>
            )}
          </>
        ) : (
          <>
            {route.caseId && !selectedDetail ? (
              <p className="ux-loading">
                {error
                  ? t("Diese Untersuchung konnte nicht geöffnet werden.")
                  : t("Dateien werden geöffnet…")}
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
                    { page: "new", caseId: r.case_id || "", runId: r.id },
                    true,
                  )
                }
              />
            )}
            <section className="ux-recent" aria-labelledby="recent-title">
              <div>
                <h2 id="recent-title">{t("Letzte Untersuchungen")}</h2>
                {cases.length + runs.filter((r) => r.chat_mode).length > 3 && (
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
                    {t("Alle anzeigen")}
                    <ArrowRight size={14} />
                  </button>
                )}
              </div>
              <Recent
                cases={cases}
                runs={runs}
                onOpen={open}
                onQuestion={(r) =>
                  navigate({ page: "new", caseId: "", runId: r.id })
                }
                limit={3}
              />
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
            {t("Erweiterter Arbeitsbereich")}
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
  onQuestion,
  limit,
}: {
  cases: Case[];
  runs: Run[];
  onOpen: (c: Case) => void;
  onQuestion: (r: Run) => void;
  limit?: number;
}) {
  useLanguage();
  const entries = [
    ...cases.map((c) => ({
      id: c.id,
      title: c.title,
      date: c.created_at,
      status: runs.find((r) => r.case_id === c.id)?.status,
      open: () => onOpen(c),
    })),
    ...runs
      .filter((r) => !r.case_id && r.chat_mode)
      .map((r) => ({
        id: r.id,
        title: r.question,
        date: r.created_at,
        status: r.status,
        open: () => onQuestion(r),
      })),
  ]
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, limit);
  return (
    <div className="ux-recent-list">
      {entries.length ? (
        entries.map((c) => {
          return (
            <button key={c.id} onClick={c.open}>
              <span>{c.title}</span>
              <small>
                {c.status ? friendlyStatus(c.status) : t("Untersuchung öffnen")}{" "}
                ·{" "}
                {new Date(c.date).toLocaleDateString(getLocale(), {
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
          {t("Deine Untersuchungen erscheinen hier.")}
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
  useLanguage();
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
  const [library, setLibrary] = useState<LibrarySelection>({ enabled: true });
  const [siemensChoice, setSiemensChoice] = useState<"auto" | "on" | "off">(
    new URLSearchParams(location.search).get("page") === "siemens"
      ? "on"
      : "auto",
  );
  const [publicQuestion, setPublicQuestion] = useState("");
  const [product, setProduct] = useState({
    family: "",
    cpu: "",
    firmware: "",
    tia_version: "",
  });
  const useSiemens =
    siemensChoice === "on" ||
    (siemensChoice === "auto" && !files.length && isSiemensQuestion(question));
  const siemensQuestion = files.length ? publicQuestion : question;
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
    setProgress(t("Demodateien werden geladen…"));
    try {
      const generated = await Promise.all(
        [
          ["inspection.csv", "inspection_data.csv"],
          ["maintenance.pdf", "maintenance_note.pdf"],
        ].map(async ([endpoint, name]) => {
          const r = await fetch(`/api/examples/${endpoint}`);
          if (!r.ok)
            throw new Error(
              t(
                "Demodateien sind nicht verfügbar. Versuche, eigene Dateien hochzuladen.",
              ),
            );
          return new File([await r.blob()], name);
        }),
      );
      add(generated);
      setPolicy("synthetic");
      setConfirmed(true);
      setQuestion(t("Warum ist der Fehlausschuss an Station S03 gestiegen?"));
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
    if (
      !question.trim() ||
      (hasNewFiles && !confirmed) ||
      (useSiemens && !siemensQuestion.trim())
    )
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
        library,
        ...(useSiemens
          ? { siemens: { question: siemensQuestion.trim(), ...product } }
          : {}),
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
        tr`${message(e)} Erfolgreich hochgeladene Dateien bleiben erhalten. Du kannst es erneut versuchen.`,
      );
    } finally {
      setBusy(false);
      onBusy(false);
      setProgress("");
    }
  }
  return (
    <>
      <div className="ux-steps" aria-label={t("Untersuchungsschritte")}>
        <span className="current">
          <b>1</b>
          {t("Frage stellen")}
        </span>
        <i />
        <span>
          <b>2</b>
          {t("Bei Bedarf Dateien hinzufügen")}
        </span>
        <i />
        <span>
          <b>3</b>
          {t("Befunde prüfen")}
        </span>
      </div>
      <div className="ux-intro">
        <h1>{t("Was möchtest du untersuchen?")}</h1>
        <p>
          {existing
            ? t(
                "Stelle eine weitere Frage zu diesen Dateien oder ergänze weitere Belege.",
              )
            : t(
                "Frage zu Siemens-SPS oder füge Dateien für eine Untersuchung hinzu.",
              )}
        </p>
      </div>
      <form className="ux-question-card" onSubmit={submit}>
        <label htmlFor="user-question">{t("Deine Frage")}</label>
        <textarea
          id="user-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t(
            "Frage zu S7 / TIA Portal oder untersuche eine Änderung in deinen Dateien…",
          )}
          maxLength={4000}
          required
          rows={3}
          disabled={busy}
        />
        <LibraryChooser value={library} onChange={setLibrary} busy={busy} />
        <details
          className="ux-siemens-options"
          open={useSiemens || isSiemensQuestion(question)}
        >
          <summary>
            {useSiemens
              ? t("Siemens-Dokumentation wird geprüft")
              : t("Siemens-Dokumentation")}
          </summary>
          <label className="ux-confirm">
            <input
              type="checkbox"
              checked={useSiemens}
              disabled={busy}
              onChange={(e) =>
                setSiemensChoice(e.target.checked ? "on" : "off")
              }
            />
            <span>
              {t("Öffentliche Siemens-Dokumentation für diese Frage verwenden")}
            </span>
          </label>
          {useSiemens && (
            <>
              {files.length > 0 && (
                <>
                  <label htmlFor="public-siemens-question">
                    {t("Öffentliche Siemens-Frage")}
                  </label>
                  <textarea
                    id="public-siemens-question"
                    value={publicQuestion}
                    onChange={(e) => setPublicQuestion(e.target.value)}
                    maxLength={500}
                    required
                    disabled={busy}
                    rows={2}
                    placeholder={t(
                      "Nur eine öffentliche Produktfrage, z. B. S7-1500 OB1 Zykluszeit",
                    )}
                  />
                </>
              )}
              <p className="ux-small">
                {t("Siemens erhält")}{" "}
                {files.length
                  ? t("nur die obige öffentliche Frage")
                  : t("deine obige Frage")}{" "}
                {t(
                  "und etwaige Produktfelder unten. Dateiinhalte und Fallverlauf bleiben lokal. Die öffentliche Suchanfrage ist auf 500 Zeichen begrenzt.",
                )}
              </p>
              <details>
                <summary>
                  {t("CPU, Firmware und TIA-Version (optional)")}
                </summary>
                <div className="ux-product-fields">
                  <label>
                    {t("SIMATIC-Familie")}
                    <select
                      value={product.family}
                      disabled={busy}
                      onChange={(e) =>
                        setProduct({ ...product, family: e.target.value })
                      }
                    >
                      <option value="">{t("Nicht angegeben")}</option>
                      {["S7-1200", "S7-1200 G2", "S7-1500"].map((f) => (
                        <option key={f}>{f}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {t("CPU-Modell")}
                    <input
                      value={product.cpu}
                      maxLength={50}
                      disabled={busy}
                      onChange={(e) =>
                        setProduct({ ...product, cpu: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Firmware
                    <input
                      value={product.firmware}
                      maxLength={12}
                      placeholder="V3.1"
                      disabled={busy}
                      onChange={(e) =>
                        setProduct({ ...product, firmware: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    TIA Portal
                    <select
                      value={product.tia_version}
                      disabled={busy}
                      onChange={(e) =>
                        setProduct({ ...product, tia_version: e.target.value })
                      }
                    >
                      <option value="">{t("Nicht angegeben")}</option>
                      {[17, 18, 19, 20, 21].map((v) => (
                        <option key={v}>V{v}</option>
                      ))}
                    </select>
                  </label>
                </div>
              </details>
            </>
          )}
        </details>
        <label
          className={`ux-add-files ${busy ? "disabled" : ""}`}
          htmlFor="user-files"
        >
          <Paperclip size={23} />
          <span>{t("CSV- oder PDF-Dateien hinzufügen")}</span>
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
                <Check
                  size={18}
                  aria-label={t("Datei bereit")}
                  className="ux-ready"
                />
              ) : (
                <button
                  type="button"
                  aria-label={tr`Entfernen: ${f.name}`}
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
            <label htmlFor="user-data-policy">{t("Dateikategorie")}</label>
            <select
              id="user-data-policy"
              value={policy}
              disabled={busy}
              onChange={(e) => {
                setPolicy(e.target.value);
                setConfirmed(false);
              }}
            >
              <option value="synthetic">
                {t("Synthetische / generierte Daten")}
              </option>
              <option value="licensed-public">
                {t("Lizenzierte öffentliche Daten")}
              </option>
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
                {t(
                  "Ich bestätige, dass diese Dateien zur Kategorie gehören und keine internen oder sensiblen Informationen enthalten.",
                )}
              </span>
            </label>
          </div>
        )}
        {error && (
          <p className="ux-error" role="alert">
            {t(error)}
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
            <span>
              {t("Nur synthetische oder lizenzierte öffentliche Daten.")}
            </span>
            {!files.length && (
              <button
                type="button"
                className="ux-link"
                disabled={busy}
                onClick={() => void example()}
              >
                {t("Demodateien ausprobieren")}
              </button>
            )}
          </div>
          <button
            className="ux-primary"
            disabled={
              busy ||
              !question.trim() ||
              (useSiemens && !siemensQuestion.trim()) ||
              (hasNewFiles && !confirmed)
            }
          >
            {busy ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <>
                {files.length ? t("Untersuchen") : t("Fragen")}
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </div>
      </form>
      <p className="ux-local">
        <LockKeyhole size={15} />
        {t("Deine Dateien werden lokal verarbeitet.")}
      </p>
    </>
  );
}
