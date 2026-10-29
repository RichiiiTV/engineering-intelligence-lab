import { useEffect, useState, type FormEvent } from "react";
import { api, post } from "./api";
import type { LibraryDocument } from "./KnowledgeLibrary";

type User = {
  id: string;
  username: string;
  role: string;
  active: boolean;
  sessions: number;
};
type AuditEvent = {
  id: number;
  at: number;
  actor: string | null;
  actor_id: string | null;
  kind: string;
  subject_id: string | null;
  details: Record<string, unknown>;
  entry_hash: string;
};
type AuditPage = {
  events: AuditEvent[];
  next_after: number | null;
  integrity: {
    valid: boolean;
    checked: number;
    head_hash?: string;
    boundary?: string;
  };
};

export default function AdminWorkspace({
  currentUserId,
  onClose,
}: {
  currentUserId: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState("documents");
  return (
    <div className="user-app">
      <main className="ux-main admin-main">
        <button className="ux-link" onClick={onClose}>
          ← Back to questions
        </button>
        <h1>Workspace administration</h1>
        <nav aria-label="Administration">
          <button
            aria-pressed={tab === "documents"}
            onClick={() => setTab("documents")}
          >
            Documents
          </button>
          <button
            aria-pressed={tab === "users"}
            onClick={() => setTab("users")}
          >
            Users
          </button>
          <button
            aria-pressed={tab === "audit"}
            onClick={() => setTab("audit")}
          >
            Audit trail
          </button>
        </nav>
        {tab === "documents" ? (
          <Documents />
        ) : tab === "users" ? (
          <Users currentUserId={currentUserId} />
        ) : (
          <Audit />
        )}
      </main>
    </div>
  );
}

function Documents() {
  const [rows, setRows] = useState<LibraryDocument[]>([]),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  async function refresh() {
    setRows(
      (await api<{ documents: LibraryDocument[] }>("/api/library/documents"))
        .documents,
    );
  }
  useEffect(() => {
    void refresh().catch((e) => setError(String(e)));
  }, []);
  async function action(work: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      await refresh();
      setNotice(message);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = new FormData(form);
    await action(
      () => api("/api/library/documents", { method: "POST", body }),
      "Document added. Index it to enable semantic search.",
    );
  }
  return (
    <section aria-label="Document administration">
      <h2>Knowledge documents</h2>
      <p>
        Active documents are available to every workspace user. Each question
        keeps its own document snapshot. Replace an edition by adding a new
        document and disabling the old one.
      </p>
      <div className="admin-list">
        {rows.map((d) => (
          <article key={d.id}>
            <h3>{d.title}</h3>
            <p>
              {d.family} · {d.version} · {d.active ? "Active" : "Disabled"}
            </p>
            <p className="ux-small">{d.license_note}</p>
            <p>
              {d.indexed_passages}/{d.passages} passages indexed for semantic
              search
            </p>
            <div className="admin-actions">
              <a href={`/api/library/documents/${d.id}/file`}>Download</a>
              <button
                disabled={busy || !d.active}
                onClick={() =>
                  void action(
                    () => post(`/api/library/documents/${d.id}/index`),
                    "Semantic index saved.",
                  )
                }
              >
                Index document
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  void action(
                    () =>
                      post(`/api/library/documents/${d.id}/availability`, {
                        active: !d.active,
                      }),
                    d.active
                      ? "Document disabled for new questions."
                      : "Document enabled.",
                  )
                }
              >
                {d.active ? "Disable" : "Enable"}
              </button>
            </div>
          </article>
        ))}
      </div>
      <details className="admin-add">
        <summary>Add a shared document</summary>
        <form onSubmit={(e) => void upload(e)} className="siemens-form">
          <label>
            Document title
            <input name="title" required maxLength={160} />
          </label>
          <label>
            Product family
            <input
              name="family"
              required
              maxLength={60}
              placeholder="For example, SIMATIC S7-1500"
            />
          </label>
          <label>
            Version / manual edition
            <input name="version" required maxLength={80} />
          </label>
          <label>
            Licence and provenance
            <input
              name="license_note"
              required
              maxLength={300}
              placeholder="State the licence that permits use and redistribution"
            />
          </label>
          <label>
            Content type
            <select name="data_policy">
              <option value="synthetic">
                Generated demonstration material
              </option>
              <option value="licensed-public">
                Explicitly licensed public material
              </option>
            </select>
          </label>
          <label>
            Source file
            <input type="file" name="file" accept=".pdf,.md,.txt" required />
          </label>
          <p className="ux-small">
            PDF: up to 10 MiB / 20 pages. UTF-8 text or Markdown: up to 1 MiB.
            No OCR. Text page numbers follow form-feed boundaries.
          </p>
          <label className="ux-confirm">
            <input type="checkbox" name="confirmed" value="true" required />
            <span>
              I confirm the licence permits sharing this document with all
              workspace users.
            </span>
          </label>
          <button className="ux-primary" disabled={busy}>
            Add document
          </button>
        </form>
      </details>
      {busy && <p role="status">Working locally…</p>}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}

function Users({ currentUserId }: { currentUserId: string }) {
  const [rows, setRows] = useState<User[]>([]),
    [next, setNext] = useState<number | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  async function refresh(offset = 0) {
    const result = await api<{ users: User[]; next_offset: number | null }>(
      `/api/auth/users?offset=${offset}&limit=50`,
    );
    setRows((old) => (offset ? [...old, ...result.users] : result.users));
    setNext(result.next_offset);
  }
  useEffect(() => {
    void refresh().catch((e) => setError(String(e)));
  }, []);
  async function action(work: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    try {
      await work();
      await refresh();
      setNotice(message);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fields = new FormData(form);
    await action(
      () => post("/api/auth/users", Object.fromEntries(fields)),
      "User account created.",
    );
    form.reset();
  }
  return (
    <section aria-label="User administration">
      <h2>Workspace users</h2>
      <p>
        Members see their own investigations and the shared library.
        Administrators also manage users, documents, storage and the workspace
        audit trail.
      </p>
      <div className="admin-list">
        {rows.map((u) => (
          <article key={u.id}>
            <h3>
              {u.username}
              {u.id === currentUserId ? " (you)" : ""}
            </h3>
            <p>
              {u.role} · {u.active ? "Active" : "Disabled"} · {u.sessions}{" "}
              active sessions
            </p>
            <div className="admin-actions">
              <button
                disabled={busy || u.id === currentUserId}
                onClick={() =>
                  void action(
                    () =>
                      post(`/api/auth/users/${u.id}/update`, {
                        role: u.role === "admin" ? "member" : "admin",
                      }),
                    "Role updated; existing sessions revoked.",
                  )
                }
              >
                {u.role === "admin" ? "Make member" : "Make administrator"}
              </button>
              <button
                disabled={busy || u.id === currentUserId}
                onClick={() =>
                  void action(
                    () =>
                      post(`/api/auth/users/${u.id}/update`, {
                        active: !u.active,
                      }),
                    "Account availability updated; disabled account sessions revoked.",
                  )
                }
              >
                {u.active ? "Disable account" : "Enable account"}
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  void action(
                    () => post(`/api/auth/users/${u.id}/revoke-sessions`),
                    "Sessions revoked.",
                  )
                }
              >
                Sign out all sessions
              </button>
            </div>
          </article>
        ))}
      </div>
      {next !== null && (
        <button disabled={busy} onClick={() => void refresh(next)}>
          Load more users
        </button>
      )}
      <details className="admin-add">
        <summary>Create a user</summary>
        <form className="siemens-form" onSubmit={(e) => void create(e)}>
          <label>
            Username
            <input
              name="username"
              minLength={3}
              maxLength={40}
              required
              autoComplete="off"
            />
          </label>
          <label>
            Initial password
            <input
              name="password"
              type="password"
              minLength={14}
              maxLength={128}
              required
              autoComplete="new-password"
            />
          </label>
          <label>
            Role
            <select name="role">
              <option value="member">Member</option>
              <option value="admin">Administrator</option>
            </select>
          </label>
          <button disabled={busy}>Create account</button>
        </form>
      </details>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}

function Audit() {
  const [page, setPage] = useState<AuditPage | null>(null),
    [events, setEvents] = useState<AuditEvent[]>([]),
    [kind, setKind] = useState(""),
    [actor, setActor] = useState(""),
    [error, setError] = useState("");
  async function refresh(after = 0) {
    try {
      const p = await api<AuditPage>(
        `/api/admin/audit?after=${after}&kind=${encodeURIComponent(kind)}&actor=${encodeURIComponent(actor)}`,
      );
      setPage(p);
      setEvents((old) => (after ? [...old, ...p.events] : p.events));
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  return (
    <section aria-label="Workspace audit trail">
      <h2>Audit trail</h2>
      <p>
        Records sign-ins, account changes, document administration, application
        writes, downloads and access denials. Questions, document contents,
        passwords and session tokens are excluded.
      </p>
      <form
        className="admin-filters"
        onSubmit={(e) => {
          e.preventDefault();
          void refresh();
        }}
      >
        <label>
          Event type
          <input
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            placeholder="For example, user_updated"
          />
        </label>
        <label>
          Actor ID
          <input
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            maxLength={40}
          />
        </label>
        <button>Apply filters</button>
      </form>
      {page && (
        <p role="status">
          {page.integrity.valid
            ? "Audit chain verified"
            : "Audit integrity check failed"}{" "}
          · {page.integrity.checked} events checked
        </p>
      )}
      <p className="ux-small">
        Append-only through the app. A local database administrator can replace
        the database; retain exported hashes independently for stronger
        assurance.
      </p>
      <a href="/api/admin/audit/export">
        Download first audit page (JSON, up to 100 events)
      </a>
      <div className="admin-audit">
        {events.map((e) => (
          <article key={e.id}>
            <strong>
              #{e.id} {e.kind}
            </strong>
            <small>
              {new Date(e.at * 1000).toLocaleString()} ·{" "}
              {e.actor || e.actor_id || "Unauthenticated"}
            </small>
            <p>{e.subject_id}</p>
            <details>
              <summary>Event metadata and integrity hash</summary>
              <pre>{JSON.stringify(e.details, null, 2)}</pre>
              <code>{e.entry_hash}</code>
            </details>
          </article>
        ))}
      </div>
      {page?.next_after != null && (
        <button onClick={() => void refresh(page.next_after!)}>
          Load more audit events
        </button>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
