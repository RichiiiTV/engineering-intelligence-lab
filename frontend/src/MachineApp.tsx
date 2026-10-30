import { useEffect, useState, type FormEvent } from "react";
import { Beaker, FolderLock, Plus, FileText, ArrowLeft } from "lucide-react";
import { api, post } from "./api";
import "./user.css";
import "./machines.css";

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
      if (selected) setDetail(await api<Detail>("/api/machines/" + selected));
    } catch (e) {
      setError(message(e));
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
        <nav aria-label="Main navigation">
          <a href="/">Ask a question</a>
          <a href="/?page=machines" aria-current="page">
            My machines
          </a>
          <a href="/?view=advanced">Advanced</a>
        </nav>
      </header>
      <main className="ux-main machine-main">
        {error && (
          <div className="ux-error" role="alert">
            {error}
            <button onClick={() => void refresh()}>Try again</button>
          </div>
        )}
        {!selected ? (
          <>
            <div className="ux-list-heading">
              <div>
                <p className="machine-eyebrow">YOUR PRIVATE KNOWLEDGE</p>
                <h1>My machines</h1>
                <p>
                  Bring your manuals, documentation and code together. Ask
                  questions with the right sources.
                </p>
              </div>
              <button className="ux-primary" onClick={() => setCreate(!create)}>
                <Plus size={18} />
                Add machine
              </button>
            </div>
            {create && (
              <form className="machine-card machine-form" onSubmit={addMachine}>
                <h2>Add a machine</h2>
                <label>
                  Machine name
                  <input
                    name="name"
                    required
                    maxLength={120}
                    placeholder="e.g. Packaging line 3"
                  />
                </label>
                <label>
                  Family (optional)
                  <input
                    name="family"
                    maxLength={60}
                    placeholder="e.g. Packaging"
                  />
                </label>
                <button className="ux-primary" disabled={busy}>
                  Create private workspace
                </button>
              </form>
            )}
            {!groups.length && !create && (
              <div className="machine-empty">
                <FolderLock size={38} />
                <h2>A workspace for each machine</h2>
                <p>
                  Add a machine, upload its sources, then start an
                  investigation. Everything stays scoped to your account.
                </p>
                <button className="ux-primary" onClick={() => setCreate(true)}>
                  Add your first machine
                </button>
              </div>
            )}
            {groups.length > 0 && (
              <>
                <p className="ux-small">
                  Related machines are grouped automatically from local document
                  embeddings. Groups organize your machines; they do not combine
                  investigation sources.
                </p>
                <div className="machine-groups">
                  {groups.map((g) => (
                    <section className="machine-card" key={g.id}>
                      <span className="machine-eyebrow">
                        {g.machines.length > 1
                          ? "AUTOMATIC SIMILARITY GROUP"
                          : g.indexed
                            ? "INDEXED WORKSPACE"
                            : "AWAITING INDEXED SOURCES"}
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
                              {m.family || "Private machine workspace"}
                            </small>
                          </span>
                          <span>Open →</span>
                        </button>
                      ))}
                    </section>
                  ))}
                </div>
              </>
            )}
          </>
        ) : !detail ? (
          <p>Opening machine workspace…</p>
        ) : (
          <>
            <button className="ux-text-button" onClick={() => select("")}>
              <ArrowLeft size={16} /> All machines
            </button>
            <div className="ux-list-heading">
              <div>
                <p className="machine-eyebrow">PRIVATE MACHINE WORKSPACE</p>
                <h1>{detail.name}</h1>
                <p>
                  {detail.family || "Manuals, documentation and source code"} ·
                  Local, read-only investigation
                </p>
              </div>
            </div>
            <div className="machine-layout">
              <section className="machine-card">
                <h2>
                  <FileText size={20} /> Sources
                </h2>
                <p className="ux-small">
                  {detail.documents.filter((d) => d.active).length}/100 active
                  sources · 10 MiB per file · PDFs up to 200 pages
                </p>
                {detail.documents.map((d) => (
                  <div className="machine-source" key={d.id}>
                    <strong>{d.title}</strong>
                    <small>
                      {d.filename} · {d.version} ·{" "}
                      {d.active ? "Available" : "Archived"} ·{" "}
                      {d.indexed_passages}/{d.passages} indexed passages
                    </small>
                    <div className="machine-actions">
                      <a
                        href={`/api/machines/${selected}/sources/${d.id}/file`}
                      >
                        Download
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
                        Preview
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
                        {d.active ? "Archive" : "Enable"}
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
                        Reindex
                      </button>
                    </div>
                  </div>
                ))}
                {!detail.documents.length && (
                  <p>
                    No sources yet. Add a manual or code export to get started.
                  </p>
                )}
                <details className="machine-upload">
                  <summary>Add manuals or code</summary>
                  <form className="machine-form" onSubmit={upload}>
                    <label>
                      Title
                      <input name="title" required maxLength={160} />
                    </label>
                    <label>
                      Edition / version
                      <input
                        name="version"
                        defaultValue="Unspecified"
                        maxLength={80}
                      />
                    </label>
                    <label>
                      Source file
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
                      I am authorized to process this material locally in my
                      private workspace.
                    </label>
                    <button className="ux-primary" disabled={busy}>
                      Upload and index
                    </button>
                    <small>
                      Code is read and inspected as text. It is never executed
                      or connected to equipment.
                    </small>
                  </form>
                </details>
                {detail.jobs.length > 0 && (
                  <details
                    open={detail.jobs.some((j) => !stopped.has(j.status))}
                  >
                    <summary>Upload activity</summary>
                    {detail.jobs.map((j) => (
                      <div className="machine-source" key={j.id}>
                        <strong>{j.filename}</strong>
                        <small>
                          {j.status} · {j.phase} · {j.progress}%
                        </small>
                        {!stopped.has(j.status) && (
                          <progress value={j.progress} max={100} />
                        )}{" "}
                        {j.error && <p className="ux-caution">{j.error}</p>}{" "}
                        {j.status !== "completed" && (
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
                            {stopped.has(j.status) ? "Retry" : "Cancel"}
                          </button>
                        )}
                      </div>
                    ))}
                  </details>
                )}
              </section>
              <section className="machine-card">
                <h2>Investigate this machine</h2>
                <p>
                  Select the sources you need and keep related questions in a
                  notebook.
                </p>
                <p className="ux-small">
                  Notebook conversations are being connected to this private
                  source selection.
                </p>
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
            {preview && (
              <section className="machine-card">
                <div className="ux-list-heading">
                  <h2>Source preview</h2>
                  <button onClick={() => setPreview(null)}>Close</button>
                </div>
                {preview.text ? (
                  <pre className="machine-code">{preview.text}</pre>
                ) : (
                  <p>Use Download to inspect the original PDF.</p>
                )}
                {preview.truncated && (
                  <p>
                    Preview limited to 40,000 characters. Download the complete
                    source above.
                  </p>
                )}
                {preview.static_review && (
                  <>
                    <p className="ux-small">{preview.static_review.scope}</p>
                    {preview.static_review.findings.map((f, i) => (
                      <p key={i}>
                        Line {f.line}: {f.message}
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
      <summary>Machine details and versions</summary>
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
            {k.replace("_", " ")}
            <input
              name={k}
              defaultValue={detail.profile[k] || ""}
              maxLength={80}
            />
          </label>
        ))}
        <button className="ux-secondary" disabled={busy}>
          Save machine details
        </button>
      </form>
    </details>
  );
}
