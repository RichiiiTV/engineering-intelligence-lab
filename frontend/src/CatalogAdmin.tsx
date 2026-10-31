import { useEffect, useState, type FormEvent } from "react";
import { Upload, FileText, FolderCheck, LoaderCircle } from "lucide-react";
import { api, post } from "./api";
import "./machines.css";
type Source = {
  id: string;
  filename: string;
  active: boolean;
  assignment_basis: string;
  classification?: {
    identity_evidence: string;
    confidence: string;
    source_kind: string;
  };
};
type Machine = {
  id: string;
  name: string;
  identity_kind: string;
  documents: Source[];
};
type Job = {
  id: string;
  filename: string;
  status: string;
  phase: string;
  progress: number;
  error?: string;
  classifier_calls?: number;
  assigned_machine_id?: string;
};
const terminal = new Set([
  "completed",
  "failed",
  "canceled",
  "interrupted",
  "timed_out",
]);
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function CatalogAdmin() {
  const [machines, setMachines] = useState<Machine[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [error, setError] = useState(""),
    [loadError, setLoadError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [chosen, setChosen] = useState<File[]>([]);
  async function refresh() {
    try {
      const result = await api<{ machines: Machine[]; jobs: Job[] }>(
        "/api/admin/machine-knowledge",
      );
      setMachines(result.machines || []);
      setJobs(result.jobs || []);
      setLoadError("");
    } catch (e) {
      setLoadError(message(e));
    }
  }
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 1800);
    return () => clearInterval(timer);
  }, []);
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
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      files = chosen.filter((f) => f.size);
    if (!(form.elements.namedItem("authorized") as HTMLInputElement).checked) {
      setError("Confirm that you may publish these files to this workspace.");
      return;
    }
    if (!files.length || files.length > 4) {
      setError("Choose one to four source files per batch.");
      return;
    }
    let accepted = 0;
    await action(async () => {
      for (const file of files) {
        const body = new FormData();
        body.set("file", file);
        body.set("authorized", "true");
        body.set("data_policy", "internal");
        await api("/api/admin/machine-knowledge/uploads", {
          method: "POST",
          body,
        });
        accepted++;
      }
      form.reset();
      setChosen([]);
      setNotice(
        `${accepted} file${accepted === 1 ? "" : "s"} queued. The backbone will extract, index and identify the machine automatically.`,
      );
    });
    if (accepted && accepted < files.length) {
      setChosen(files.slice(accepted));
      setNotice(
        `${accepted} files were accepted. Wait for indexing before submitting the remaining files; accepted files remain in Upload activity.`,
      );
    }
  }
  return (
    <section aria-label="Machine knowledge administration">
      <h2>Machine knowledge</h2>
      <p>
        Add manuals, documentation and code exports. The backbone reads the
        files, creates local embeddings and assigns them to machine knowledge
        automatically.
      </p>
      <form className="machine-card machine-form" onSubmit={upload}>
        <h3>
          <Upload size={19} />
          Add machine data
        </h3>
        <label>
          Source files
          <input
            name="files"
            aria-label="Machine source files"
            type="file"
            multiple
            onChange={(e) => setChosen(Array.from(e.target.files || []))}
            accept=".pdf,.md,.txt,.st,.scl,.awl,.py,.js,.ts,.c,.cpp,.h,.xml,.json,.yaml,.yml,.cfg,.ini,.csv"
          />
        </label>
        {chosen.length > 0 && (
          <p className="ux-small">
            Pending files: {chosen.map((f) => f.name).join(", ")}
          </p>
        )}
        <p className="ux-small">
          Up to four files per batch. No machine name or source selection is
          required. Files are published to signed-in users in this workspace
          after processing.
        </p>
        <label className="machine-check">
          <input name="authorized" type="checkbox" required />I am authorized to
          make these files available to users in this workspace.
        </label>
        <button className="ux-primary" disabled={busy}>
          {busy ? <LoaderCircle size={17} /> : <Upload size={17} />}Upload and
          organize automatically
        </button>
      </form>
      {(error || loadError) && (
        <p className="ux-error" role="alert">
          {error || loadError}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {jobs.length > 0 && (
        <section className="machine-card">
          <h3>Upload activity</h3>
          {jobs.slice(0, 15).map((j) => (
            <div className="machine-source" key={j.id}>
              <strong>{j.filename}</strong>
              <small>
                {j.status === "completed"
                  ? "Ready"
                  : j.phase === "classifying"
                    ? "Identifying machine…"
                    : j.phase}{" "}
                · {j.progress}%
                {j.classifier_calls
                  ? ` · classification attempts ${j.classifier_calls}/3`
                  : ""}
              </small>
              {!terminal.has(j.status) && (
                <progress value={j.progress} max={100} />
              )}{" "}
              {j.error && <p className="ux-caution">{j.error}</p>}{" "}
              {j.status !== "completed" && j.phase !== "discarded" && (
                <div className="machine-actions">
                  <button
                    disabled={busy}
                    onClick={() =>
                      void action(() =>
                        post(
                          `/api/admin/machine-knowledge/jobs/${j.id}/${terminal.has(j.status) ? "retry" : "cancel"}`,
                        ),
                      )
                    }
                  >
                    {terminal.has(j.status) ? "Retry" : "Cancel"}
                  </button>
                  {terminal.has(j.status) && (
                    <details>
                      <summary>Discard staged upload</summary>
                      <p>
                        Discard only the staged upload bytes. This job cannot be
                        retried afterwards. Published sources and answers are
                        retained.
                      </p>
                      <button
                        onClick={() =>
                          void action(() =>
                            post(
                              `/api/admin/machine-knowledge/jobs/${j.id}/discard`,
                              { confirmation: "DISCARD STAGED UPLOAD" },
                            ),
                          )
                        }
                      >
                        Confirm discard
                      </button>
                    </details>
                  )}
                </div>
              )}
            </div>
          ))}
        </section>
      )}
      <h3>
        <FolderCheck size={20} />
        Automatically organized knowledge
      </h3>
      {!machines.length && (
        <p className="ux-small">
          Upload files to build the machine knowledge backbone. Existing private
          workspaces are kept separate.
        </p>
      )}
      <div className="machine-groups">
        {machines.map((m) => (
          <section className="machine-card" key={m.id}>
            <span className="machine-eyebrow">
              {m.identity_kind === "unknown"
                ? "IDENTITY NOT ESTABLISHED"
                : m.identity_kind === "product_family"
                  ? "PRODUCT FAMILY"
                  : "MACHINE KNOWLEDGE"}
            </span>
            <h2>{m.name}</h2>
            {m.identity_kind === "unknown" && (
              <p className="ux-caution">
                No supported machine identity was found. The chat will ask for
                clarification rather than assume a machine.
              </p>
            )}
            {m.documents.map((d) => (
              <details className="machine-source" key={d.id}>
                <summary>
                  <FileText size={14} /> {d.filename} ·{" "}
                  {d.active ? "Available" : "Archived"}
                </summary>
                <p className="ux-small">
                  Assignment:{" "}
                  {d.assignment_basis === "semantic-inference"
                    ? "Embedding and LLM inference"
                    : d.assignment_basis === "source-identity"
                      ? "Identifier found in source"
                      : "Unidentified"}{" "}
                  · {d.classification?.confidence || "unknown"} extraction
                  confidence
                </p>
                {d.classification?.identity_evidence && (
                  <blockquote>{d.classification.identity_evidence}</blockquote>
                )}
                <div className="machine-actions">
                  <a
                    href={`/api/admin/machine-knowledge/documents/${d.id}/file`}
                  >
                    Download original
                  </a>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void action(() =>
                        post(
                          `/api/admin/machine-knowledge/documents/${d.id}/availability`,
                          { active: !d.active },
                        ),
                      )
                    }
                  >
                    {d.active ? "Archive for future answers" : "Enable"}
                  </button>
                </div>
              </details>
            ))}
          </section>
        ))}
      </div>
      <p className="ux-small">
        Users only describe their problem and attach images or logs. Machine
        matching, source retrieval and conversation context are handled by the
        backbone. Their chats and attachments are not added to this shared
        knowledge.
      </p>
    </section>
  );
}
