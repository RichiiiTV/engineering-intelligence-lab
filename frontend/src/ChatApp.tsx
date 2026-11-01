import { useLanguage, t } from "./i18n";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  Beaker,
  Paperclip,
  ArrowUp,
  Plus,
  X,
  MessageSquare,
  LoaderCircle,
} from "lucide-react";
import { api, post } from "./api";
import { useCurrentUser } from "./AuthGate";
import type { EvidenceReport, Run } from "./types";
import { stopped } from "./useInvestigation";
import { friendlyStatus } from "./userFlow";
import SafeAnswer from "./SafeAnswer";
import SourceReader, { SourceCard } from "./SourceReader";
import { LibraryReferences } from "./KnowledgeLibrary";
import SiemensReferences from "./SiemensReferences";
import { displayNotice } from "./locale";
import { getLanguage } from "./i18n";
import "./user.css";
import "./machines.css";
import "./chat.css";

type Conversation = { id: string; title: string };
type Attachment = { id: string; filename: string; kind: string };
type Detail = Conversation & { turns: Run[]; attachments: Attachment[] };
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function ChatApp() {
  useLanguage();
  const user = useCurrentUser();
  const [selected, setSelected] = useState(
      new URLSearchParams(location.search).get("chat") || "",
    ),
    [detail, setDetail] = useState<Detail | null>(null);
  const [rows, setRows] = useState<Conversation[]>([]),
    [historyOpen, setHistoryOpen] = useState(false);
  const [question, setQuestion] = useState(""),
    [files, setFiles] = useState<File[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [loadError, setLoadError] = useState("");
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const refreshRequest = useRef<AbortController | null>(null),
    refreshVersion = useRef(0);
  const active = Boolean(detail?.turns.some((r) => !stopped.has(r.status)));
  const submission = useRef<{ signature: string; id: string } | null>(null),
    input = useRef<HTMLInputElement>(null);
  const refresh = useCallback(async () => {
    const conversationId = selectedRef.current;
    refreshRequest.current?.abort();
    const controller = new AbortController();
    refreshRequest.current = controller;
    const version = ++refreshVersion.current;
    const current = () =>
      !controller.signal.aborted &&
      version === refreshVersion.current &&
      conversationId === selectedRef.current;
    try {
      const [list, result] = await Promise.all([
        api<{ conversations: Conversation[] }>("/api/chat/conversations", {
          signal: controller.signal,
        }).then((list) => {
          if (current()) setRows(list.conversations);
          return list;
        }),
        conversationId
          ? api<Detail>("/api/chat/conversations/" + conversationId, {
              signal: controller.signal,
            })
          : Promise.resolve(null),
      ]);
      if (!current()) return;
      setRows(list.conversations);
      if (result) setDetail(result);
      setLoadError("");
    } catch (e) {
      if (current()) setLoadError(message(e));
      controller.abort();
    }
  }, []);
  useEffect(() => {
    setDetail(null);
    setLoadError("");
    if (document.visibilityState !== "hidden") void refresh();
    return () => {
      ++refreshVersion.current;
      refreshRequest.current?.abort();
    };
  }, [selected, refresh]);
  useEffect(() => {
    let disposed = false,
      pending = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const visible = () => document.visibilityState !== "hidden";
    async function poll() {
      if (disposed || pending || !visible()) return;
      pending = true;
      await refresh();
      pending = false;
      if (!disposed && active && visible())
        timer = setTimeout(() => void poll(), 1500);
    }
    const visibility = () => {
      clearTimeout(timer);
      if (!visible()) {
        refreshRequest.current?.abort();
      } else void poll();
    };
    if (active && visible()) timer = setTimeout(() => void poll(), 1500);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      disposed = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [selected, active, refresh]);
  function select(id: string) {
    selectedRef.current = id;
    setSelected(id);
    setHistoryOpen(false);
    setQuestion("");
    setFiles([]);
    setError("");
    submission.current = null;
    history.pushState(null, "", id ? "/?chat=" + id : "/");
  }
  useEffect(() => {
    const pop = () => {
      const id = new URLSearchParams(location.search).get("chat") || "";
      selectedRef.current = id;
      setSelected(id);
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  function attach(next: FileList | null) {
    if (!next) return;
    const all = [...files, ...Array.from(next)];
    if (
      all.length > 4 ||
      all.reduce((n, f) => n + f.size, 0) > 10 * 1024 * 1024
    ) {
      setError(t("Bis zu vier Dateien mit insgesamt 10 MiB anhängen."));
      return;
    }
    if (all.filter((f) => f.type.startsWith("image/")).length > 2) {
      setError(t("Höchstens zwei Bilder anhängen."));
      return;
    }
    setFiles(all);
    setError("");
    if (input.current) input.current.value = "";
  }
  async function ask(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const signature = JSON.stringify({
      language: getLanguage(),
      selected,
      question,
      files: files.map((f) => [f.name, f.size, f.lastModified]),
    });
    if (submission.current?.signature !== signature)
      submission.current = { signature, id: crypto.randomUUID() };
    const body = new FormData();
    body.set("question", question.trim());
    body.set("language", getLanguage());
    body.set("request_id", submission.current.id);
    if (selected) body.set("conversation_id", selected);
    files.forEach((f) => body.append("files", f));
    try {
      const run = await api<Run>("/api/chat/questions", {
        method: "POST",
        body,
      });
      const id = run.chat_context!.id;
      if (selectedRef.current !== selected) {
        await refresh();
        return;
      }
      setQuestion((current) => (current === question ? "" : current));
      setFiles((current) => (current === files ? [] : current));
      submission.current = null;
      if (id !== selected) {
        selectedRef.current = id;
        setSelected(id);
        history.replaceState(null, "", "/?chat=" + id);
      } else await refresh();
    } catch (e) {
      if (selectedRef.current === selected) setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="user-app chat-app">
      <header className="ux-header">
        <a className="ux-brand" href="/">
          <Beaker size={28} />
          <span>Engineering Intelligence Lab</span>
        </a>
        <nav aria-label={t("Chat-Navigation")}>
          <button
            onClick={() => {
              if (!historyOpen) void refresh();
              setHistoryOpen(!historyOpen);
            }}
          >
            <MessageSquare size={17} />
            {t("Deine Chats")}
          </button>
          <button onClick={() => select("")} disabled={busy}>
            <Plus size={17} />
            {t("Neuer Chat")}
          </button>
          {user?.role === "admin" && (
            <a href="/?view=advanced">{t("Erweitert")}</a>
          )}
        </nav>
      </header>
      {historyOpen && (
        <aside className="chat-history">
          <h2>{t("Deine Chats")}</h2>
          {rows.map((r) => (
            <button key={r.id} onClick={() => select(r.id)}>
              {r.title}
            </button>
          ))}
          {!rows.length && <p>{t("Noch keine Chats.")}</p>}
        </aside>
      )}
      <main className={"chat-main" + (!selected ? " chat-empty" : "")}>
        {!selected ? (
          <div className="chat-welcome">
            <span className="chat-mark">
              <Beaker size={27} />
            </span>
            <h1>{t("Was ist mit deiner Maschine los?")}</h1>
            <p>
              {t(
                "Beschreibe das Problem. Füge bei Bedarf ein Foto oder Fehlerprotokoll hinzu.",
              )}
              <br />
              {t(
                "Ich suche das passende Maschinenwissen und helfe dir bei der Untersuchung.",
              )}
            </p>
          </div>
        ) : !detail ? (
          <p className="ux-loading">{t("Chat wird geöffnet…")}</p>
        ) : (
          <section
            className="chat-conversation"
            aria-label={t("Problemgespräch")}
          >
            {detail.turns.map((run) => (
              <ChatTurn
                key={run.id}
                run={run}
                attachments={detail.attachments.filter((a) =>
                  run.chat_context?.submitted_attachment_ids?.includes(a.id),
                )}
                refresh={refresh}
              />
            ))}
          </section>
        )}
        <form className="chat-composer" onSubmit={ask}>
          <label className="chat-question-label" htmlFor="problem-question">
            {selected ? t("Gespräch fortsetzen") : t("Beschreibe dein Problem")}
          </label>
          <textarea
            id="problem-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={t(
              "z. B. Meine Maschine XY mit Siemens S7-1500 zeigt den Fehlercode 16#80A1. Was soll ich prüfen?",
            )}
            rows={3}
            required
            maxLength={4000}
          />
          {files.length > 0 && (
            <div className="chat-file-list">
              {files.map((f, i) => (
                <span key={i}>
                  <Paperclip size={14} />
                  {f.name}
                  <button
                    type="button"
                    aria-label={t("Entfernen: ") + f.name}
                    onClick={() => setFiles(files.filter((_, n) => n !== i))}
                  >
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="chat-composer-actions">
            <input
              ref={input}
              aria-label={t("Bilder oder Fehlerprotokolle anhängen")}
              type="file"
              multiple
              accept=".png,.jpg,.jpeg,.webp,.log,.txt,.csv,.json"
              onChange={(e) => attach(e.target.files)}
              hidden
            />
            <button
              className="chat-attach"
              type="button"
              onClick={() => input.current?.click()}
              disabled={busy}
            >
              <Paperclip size={19} />
              {t("Bilder oder Protokolle hinzufügen")}
            </button>
            <button
              className="chat-send"
              aria-label={t("Problem senden")}
              disabled={busy || active || !question.trim()}
            >
              {busy || active ? (
                <LoaderCircle size={20} className="chat-spinner" />
              ) : (
                <ArrowUp size={21} />
              )}
            </button>
          </div>
        </form>
        {/^\/siemens\b/i.test(question) && (
          <p className="ux-caution">
            {t(
              "Nur die öffentliche Frage nach /siemens wird an Siemens gesendet. Interne Namen und Details bitte weglassen. Bilder, Protokolle und Chatverlauf bleiben lokal.",
            )}
          </p>
        )}
        {(error || loadError) && (
          <p className="ux-error" role="alert">
            {t(error || loadError)}
          </p>
        )}
        {loadError && (
          <button type="button" onClick={() => void refresh()}>
            {t("Erneut versuchen")}
          </button>
        )}
        <p className="chat-footnote">
          {t(
            "Bei eindeutiger Siemens-SPS-Diagnose suche ich automatisch öffentlich nach Produktfamilie und eingegebenem Fehlercode. Interne Namen und Anhänge werden dabei nicht übertragen. Mit „nur lokal“ bleibt die Frage lokal. Chats und Anhänge bleiben privat. Prüfe vorgeschlagene Maßnahmen, bevor du sie umsetzt.",
          )}
        </p>
      </main>
    </div>
  );
}

function ChatTurn({
  run,
  attachments,
  refresh,
}: {
  run: Run;
  attachments: Attachment[];
  refresh: () => Promise<void>;
}) {
  useLanguage();
  const [report, setReport] = useState<EvidenceReport | null>(null),
    [error, setError] = useState("");
  const [openSource, setOpenSource] = useState<string | null>(null);
  useEffect(() => {
    if (!stopped.has(run.status)) return;
    const c = new AbortController();
    void api<EvidenceReport>("/api/investigations/" + run.id + "/export", {
      signal: c.signal,
    })
      .then(setReport)
      .catch((e) => {
        if (!c.signal.aborted) setError(message(e));
      });
    return () => c.abort();
  }, [run.id, run.status]);
  const refs = [
    ...(report?.library_citations || []),
    ...(report?.problem_citations || []),
    ...(report?.external_references || []),
  ];
  const localSources = [
    ...(report?.library_citations || []),
    ...(report?.problem_citations || []),
  ];
  const selectedSource = localSources.find((r) => r.citation_id === openSource);
  return (
    <article className="chat-turn">
      <div className="chat-human">
        <p>{run.question}</p>
        {attachments.map((a) => (
          <div key={a.id}>
            {a.kind === "image" ? (
              <img
                className="chat-thumbnail"
                alt={a.filename}
                src={"/api/chat/attachments/" + a.id + "/preview"}
              />
            ) : (
              <span className="chat-attachment-name">
                <Paperclip size={14} />
                {a.filename}
              </span>
            )}
          </div>
        ))}
      </div>
      {!stopped.has(run.status) ? (
        <div className="chat-thinking">
          <LoaderCircle size={17} className="chat-spinner" />
          <span>
            {run.status === "queued"
              ? t("Wartet auf die Untersuchung…")
              : t("Problem und Maschinenwissen werden geprüft…")}
          </span>
          <button
            onClick={() =>
              void post("/api/investigations/" + run.id + "/cancel")
                .then(refresh)
                .catch((e) => setError(message(e)))
            }
          >
            {t("Stoppen")}
          </button>
        </div>
      ) : (
        <div className="chat-assistant">
          {run.status !== "completed" && (
            <p className="ux-caution">
              {friendlyStatus(run.status)}.{" "}
              {run.status === "budget_exceeded"
                ? t(
                    "Stelle eine gezieltere Rückfrage, um die Untersuchung fortzusetzen.",
                  )
                : run.status === "cancelled"
                  ? t("Du kannst mit einer weiteren Frage fortfahren.")
                  : t(
                      "Die Untersuchung konnte nicht abgeschlossen werden. Versuche es erneut oder ergänze relevante Fehlerangaben.",
                    )}
            </p>
          )}
          {report?.catalog_routing?.machine && (
            <p className="chat-machine-tag">
              {report.catalog_routing.machine.basis.includes("inference") ||
              report.catalog_routing.machine.basis.includes("model")
                ? t("Vermutete Maschine: ")
                : t("Maschine: ")}
              {report.catalog_routing.machine.name}
            </p>
          )}
          {run.status === "completed" &&
            report?.answer_contract?.outcome === "needs_review" && (
              <p className="ux-caution">
                {t("Die Quellen dieser Antwort müssen geprüft werden.")}{" "}
                {report.answer_contract.issues.map(displayNotice).join(" ")}
              </p>
            )}
          {report?.answer_contract?.outcome === "budget_limited" && (
            <p className="ux-caution">
              {t(
                "Teilweise Belegprüfung: Diese Antwort hat ihr Untersuchungsbudget erreicht.",
              )}
            </p>
          )}
          {(report?.answer || run.result?.answer) && (
            <SafeAnswer
              text={
                report?.answer ||
                run.result?.answer ||
                t("Keine abschließende Antwort erhalten.")
              }
              references={refs}
              prefix={run.id + "-"}
              onOpenSource={setOpenSource}
            />
          )}
          {report?.attachment_notice && (
            <p className="ux-caution">
              {displayNotice(report.attachment_notice)}
            </p>
          )}
          {report?.integrations?.siemens?.enabled && refs.length === 0 && (
            <SiemensReferences report={report} />
          )}
          {report && refs.length > 0 && (
            <details className="chat-sources">
              <summary>
                {t("Quellen ·")} {refs.length}
              </summary>
              {((report.library_citations || []).length > 0 ||
                report.catalog_routing?.status === "identified") && (
                <LibraryReferences
                  report={report}
                  runId={run.id}
                  prefix={run.id + "-"}
                  onOpenSource={setOpenSource}
                />
              )}
              <SiemensReferences report={report} />
              {report.problem_citations?.map((r, i) => (
                <SourceCard
                  key={r.citation_id}
                  source={r}
                  number={(report.library_citations?.length || 0) + i + 1}
                  onOpen={setOpenSource}
                />
              ))}
            </details>
          )}
        </div>
      )}
      {error && (
        <p className="ux-error" role="alert">
          {t(error)}
        </p>
      )}
      {selectedSource && (
        <SourceReader
          key={selectedSource.citation_id}
          source={selectedSource}
          number={localSources.indexOf(selectedSource) + 1}
          runId={run.id}
          onClose={() => setOpenSource(null)}
        />
      )}
    </article>
  );
}
