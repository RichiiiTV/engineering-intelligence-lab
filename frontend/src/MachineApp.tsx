import { useEffect, useRef, useState, type FormEvent } from "react";
import { Beaker, FolderLock, Plus, FileText, ArrowLeft } from "lucide-react";
import { api, post } from "./api";
import { statusLabel } from "./locale";
import "./user.css";
import "./machines.css";
import NotebookPanel from "./NotebookPanel";

export type Machine = {
  id: string;
  name: string;
  family: string;
  profile: Record<string, string>;
};
export type Source = {
  id: string;
  title: string;
  filename: string;
  version: string;
  active: boolean;
  sha256: string;
  passages: number;
  indexed_passages: number;
};
type Job = {
  id: string;
  filename: string;
  status: string;
  phase: string;
  progress: number;
  error?: string;
};
type Detail = Machine & { documents: Source[]; jobs: Job[] };
type Group = {
  id: string;
  label: string;
  indexed: boolean;
  machines: Machine[];
};
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const stopped = new Set([
  "completed",
  "failed",
  "canceled",
  "interrupted",
  "timed_out",
]);

export default function MachineApp() {
  const [groups, setGroups] = useState<Group[]>([]),
    [detail, setDetail] = useState<Detail | null>(null);
  const [selected, setSelected] = useState(
    new URLSearchParams(location.search).get("machine") || "",
  );
  const [create, setCreate] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const [preview, setPreview] = useState<{
    text?: string;
    truncated?: boolean;
    static_review?: {
      scope: string;
      findings: { line: number; message: string }[];
    };
  } | null>(null);
  async function refresh() {
    try {
      const data = await api<{ groups: Group[] }>("/api/machines/groups");
      setGroups(data.groups);
      if (selected) {
        const result = await api<Detail>("/api/machines/" + selected);
        if (selectedRef.current === selected) setDetail(result);
      }
      setLoadError("");
    } catch (e) {
      setLoadError(message(e));
    }
  }
  useEffect(() => {
    setDetail(null);
    void refresh();
    const timer = setInterval(() => void refresh(), 2500);
    return () => clearInterval(timer);
  }, [selected]);
  function select(id: string) {
    setSelected(id);
    setPreview(null);
    history.replaceState(
      null,
      "",
      `/?page=machines${id ? "&machine=" + id : ""}`,
    );
  }
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
      return true;
    } catch (e) {
      setError(message(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function addMachine(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      data = new FormData(form);
    await action(async () => {
      const m = await post<Machine>("/api/machines", {
        name: data.get("name"),
        family: data.get("family"),
      });
      setCreate(false);
      select(m.id);
    });
  }
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const ok = await action(() =>
      api(`/api/machines/${selected}/sources`, {
        method: "POST",
        body: new FormData(form),
      }),
    );
    if (ok) form.reset();
  }
  return (
    <div className="user-app">
      <header className="ux-header">
        <a className="ux-brand" href="/">
          <Beaker size={29} />
          <span>Engineering Intelligence Lab</span>
        </a>
        <nav aria-label="Hauptnavigation">
          <a href="/">Frage stellen</a>
          <a href="/?page=machines" aria-current="page">
            Meine Maschinen
          </a>
          <a href="/?view=advanced">Erweitert</a>
        </nav>
      </header>
      <main className="ux-main machine-main">
        {(error || loadError) && (
          <div className="ux-error" role="alert">
            {error || loadError}
            <button onClick={() => void refresh()}>Erneut versuchen</button>
          </div>
        )}
        {!selected ? (
          <>
            <div className="ux-list-heading">
              <div>
                <p className="machine-eyebrow">DEIN PRIVATES WISSEN</p>
                <h1>Meine Maschinen</h1>
                <p>
                  Handbücher, Dokumentation und Code zusammenführen. Fragen mit
                  passenden Quellen beantworten.
                </p>
              </div>
              <button className="ux-primary" onClick={() => setCreate(!create)}>
                <Plus size={18} />
                Maschine hinzufügen
              </button>
            </div>
            {create && (
              <form className="machine-card machine-form" onSubmit={addMachine}>
                <h2>Maschine hinzufügen</h2>
                <label>
                  Maschinenname
                  <input
                    name="name"
                    required
                    maxLength={120}
                    placeholder="z. B. Verpackungslinie 3"
                  />
                </label>
                <label>
                  Familie (optional)
                  <input
                    name="family"
                    maxLength={60}
                    placeholder="z. B. Verpackung"
                  />
                </label>
                <button className="ux-primary" disabled={busy}>
                  Privaten Arbeitsbereich erstellen
                </button>
              </form>
            )}
            {!groups.length && !create && (
              <div className="machine-empty">
                <FolderLock size={38} />
                <h2>Ein Arbeitsbereich pro Maschine</h2>
                <p>
                  Maschine hinzufügen, Quellen hochladen und eine Untersuchung
                  starten. Alles bleibt auf dein Konto beschränkt.
                </p>
                <button className="ux-primary" onClick={() => setCreate(true)}>
                  Erste Maschine hinzufügen
                </button>
              </div>
            )}
            {groups.length > 0 && (
              <>
                <p className="ux-small">
                  Verwandte Maschinen werden automatisch anhand lokaler
                  Dokument-Embeddings gruppiert. Gruppen ordnen deine Maschinen;
                  sie führen keine Untersuchungsquellen zusammen.
                </p>
                <div className="machine-groups">
                  {groups.map((g) => (
                    <section className="machine-card" key={g.id}>
                      <span className="machine-eyebrow">
                        {g.machines.length > 1
                          ? "AUTOMATISCHE ÄHNLICHKEITSGRUPPE"
                          : g.indexed
                            ? "INDEXIERTER ARBEITSBEREICH"
                            : "WARTET AUF INDEXIERTE QUELLEN"}
                      </span>
                      <h2>{g.label}</h2>
                      {g.machines.map((m) => (
                        <button
                          className="machine-link"
                          onClick={() => select(m.id)}
                          key={m.id}
                        >
                          <FolderLock size={20} />
                          <span>
                            <strong>{m.name}</strong>
                            <small>
                              {m.family || "Privater Maschinenarbeitsbereich"}
                            </small>
                          </span>
                          <span>Öffnen →</span>
                        </button>
                      ))}
                    </section>
                  ))}
                </div>
              </>
            )}
          </>
        ) : !detail ? (
          <p>Maschinenarbeitsbereich wird geöffnet…</p>
        ) : (
          <>
            <button className="ux-text-button" onClick={() => select("")}>
              <ArrowLeft size={16} /> Alle Maschinen
            </button>
            <div className="ux-list-heading">
              <div>
                <p className="machine-eyebrow">
                  PRIVATER MASCHINENARBEITSBEREICH
                </p>
                <h1>{detail.name}</h1>
                <p>
                  {detail.family || "Handbücher, Dokumentation und Quellcode"} ·
                  Lokale Untersuchung mit rein lesendem Zugriff
                </p>
              </div>
            </div>
            <div className="machine-layout">
              <section className="machine-card">
                <h2>
                  <FileText size={20} /> Quellen
                </h2>
                <p className="ux-small">
                  {detail.documents.filter((d) => d.active).length}/100 aktive
                  Quellen · 10 MiB pro Datei · PDFs bis 200 Seiten
                </p>
                {detail.documents.map((d) => (
                  <div className="machine-source" key={d.id}>
                    <strong>{d.title}</strong>
                    <small>
                      {d.filename} · {d.version} ·{" "}
                      {d.active ? "Verfügbar" : "Archiviert"} ·{" "}
                      {d.indexed_passages}/{d.passages} indexierte Abschnitte
                    </small>
                    <div className="machine-actions">
                      <a
                        href={`/api/machines/${selected}/sources/${d.id}/file`}
                      >
                        Herunterladen
                      </a>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void action(async () =>
                            setPreview(
                              await api(
                                `/api/machines/${selected}/sources/${d.id}/preview`,
                              ),
                            ),
                          )
                        }
                      >
                        Vorschau
                      </button>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void action(() =>
                            post(
                              `/api/machines/${selected}/sources/${d.id}/availability`,
                              { active: !d.active },
                            ),
                          )
                        }
                      >
                        {d.active ? "Archivieren" : "Aktivieren"}
                      </button>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void action(() =>
                            post(
                              `/api/machines/${selected}/sources/${d.id}/index`,
                            ),
                          )
                        }
                      >
                        Neu indexieren
                      </button>
                    </div>
                  </div>
                ))}
                {!detail.documents.length && (
                  <p>
                    Noch keine Quellen. Füge ein Handbuch oder einen Code-Export
                    hinzu.
                  </p>
                )}
                <details className="machine-upload">
                  <summary>Handbücher oder Code hinzufügen</summary>
                  <form className="machine-form" onSubmit={upload}>
                    <label>
                      Titel
                      <input name="title" required maxLength={160} />
                    </label>
                    <label>
                      Ausgabe / Version
                      <input
                        name="version"
                        defaultValue="Nicht angegeben"
                        maxLength={80}
                      />
                    </label>
                    <label>
                      Quelldatei
                      <input
                        type="file"
                        name="file"
                        required
                        accept=".pdf,.txt,.md,.st,.scl,.awl,.py,.js,.ts,.c,.cpp,.h,.xml,.json,.yaml,.yml,.cfg,.ini,.csv"
                      />
                    </label>
                    <input name="data_policy" type="hidden" value="internal" />
                    <label className="machine-check">
                      <input
                        name="authorized"
                        type="checkbox"
                        value="true"
                        required
                      />
                      Ich bin berechtigt, dieses Material lokal in meinem
                      privaten Arbeitsbereich zu verarbeiten.
                    </label>
                    <button className="ux-primary" disabled={busy}>
                      Hochladen und indexieren
                    </button>
                    <small>
                      Code wird als Text gelesen und geprüft. Er wird niemals
                      ausgeführt oder mit Anlagen verbunden.
                    </small>
                  </form>
                </details>
                {detail.jobs.length > 0 && (
                  <details
                    open={detail.jobs.some((j) => !stopped.has(j.status))}
                  >
                    <summary>Upload-Aktivitäten</summary>
                    {detail.jobs.map((j) => (
                      <div className="machine-source" key={j.id}>
                        <strong>{j.filename}</strong>
                        <small>
                          {statusLabel(j.status)} · {statusLabel(j.phase)} ·{" "}
                          {j.progress}%
                        </small>
                        {!stopped.has(j.status) && (
                          <progress value={j.progress} max={100} />
                        )}{" "}
                        {j.error && <p className="ux-caution">{j.error}</p>}{" "}
                        {j.status !== "completed" &&
                          j.phase !== "discarded" && (
                            <button
                              disabled={busy}
                              onClick={() =>
                                void action(() =>
                                  post(
                                    `/api/machines/${selected}/jobs/${j.id}/${stopped.has(j.status) ? "retry" : "cancel"}`,
                                  ),
                                )
                              }
                            >
                              {stopped.has(j.status)
                                ? "Erneut versuchen"
                                : "Abbrechen"}
                            </button>
                          )}
                        {stopped.has(j.status) &&
                          j.status !== "completed" &&
                          j.phase !== "discarded" && (
                            <details>
                              <summary>
                                Zwischengespeicherten Upload verwerfen
                              </summary>
                              <p className="ux-small">
                                Zwischengespeicherte Daten entfernen für{" "}
                                {j.filename}. Danach ist kein erneuter Versuch
                                dieses Auftrags möglich. Veröffentlichte und
                                aufbewahrte Quellen und Antworten bleiben
                                verfügbar. Lade bei Bedarf die Originaldatei
                                erneut hoch.
                              </p>
                              <button
                                disabled={busy}
                                onClick={() =>
                                  void action(() =>
                                    post(
                                      `/api/machines/${selected}/jobs/${j.id}/discard`,
                                      { confirmation: "DISCARD STAGED UPLOAD" },
                                    ),
                                  )
                                }
                              >
                                Verwerfen des zwischengespeicherten Uploads
                                bestätigen
                              </button>
                            </details>
                          )}
                      </div>
                    ))}
                  </details>
                )}
              </section>
              <div>
                <NotebookPanel
                  key={selected}
                  machineId={selected}
                  sources={detail.documents}
                />
                <section className="machine-card">
                  <MachineProfile
                    detail={detail}
                    busy={busy}
                    save={(data) =>
                      action(() =>
                        post(`/api/machines/${selected}/profile`, data),
                      )
                    }
                  />
                </section>
              </div>
            </div>
            {preview && (
              <section className="machine-card">
                <div className="ux-list-heading">
                  <h2>Quellenvorschau</h2>
                  <button onClick={() => setPreview(null)}>Schließen</button>
                </div>
                {preview.text ? (
                  <pre className="machine-code">{preview.text}</pre>
                ) : (
                  <p>Nutze den Download, um das Original-PDF zu prüfen.</p>
                )}
                {preview.truncated && (
                  <p>
                    Vorschau auf 40.000 Zeichen begrenzt. Lade oben die
                    vollständige Quelle herunter.
                  </p>
                )}
                {preview.static_review && (
                  <>
                    <p className="ux-small">{preview.static_review.scope}</p>
                    {preview.static_review.findings.map((f, i) => (
                      <p key={i}>
                        Zeile {f.line}: {f.message}
                      </p>
                    ))}
                  </>
                )}
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function MachineProfile({
  detail,
  busy,
  save,
}: {
  detail: Detail;
  busy: boolean;
  save: (data: unknown) => Promise<boolean>;
}) {
  return (
    <details className="machine-upload">
      <summary>Maschinendetails und Versionen</summary>
      <form
        className="machine-form"
        key={detail.id}
        onSubmit={(e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          void save({
            name: detail.name,
            family: detail.family,
            profile: Object.fromEntries(
              ["family", "model", "firmware", "software_version"].map((k) => [
                k,
                data.get(k) || "",
              ]),
            ),
          });
        }}
      >
        {["family", "model", "firmware", "software_version"].map((k) => (
          <label key={k}>
            {
              (
                {
                  family: "Familie",
                  model: "Modell",
                  firmware: "Firmware",
                  software_version: "Software-Version",
                } as Record<string, string>
              )[k]
            }
            <input
              name={k}
              defaultValue={detail.profile[k] || ""}
              maxLength={80}
            />
          </label>
        ))}
        <button className="ux-secondary" disabled={busy}>
          Maschinendetails speichern
        </button>
      </form>
    </details>
  );
}
