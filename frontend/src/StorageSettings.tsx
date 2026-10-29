import { useEffect, useState } from "react";
import { api, post } from "./api";

type CaseRow = { id: string; title: string; deleted_at?: string };
type Plan = {
  id: string;
  sha256: string;
  expires_at: string;
  cases: CaseRow[];
};
type Storage = {
  databases: { name: string; logical_bytes: number; limit_bytes: number }[];
  backups: { id: string; size: number; sha256: string }[];
};
const CONFIRM = "PERMANENTLY PURGE REVIEWED TRASH";

export default function StorageSettings({ admin }: { admin: boolean }) {
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [trash, setTrash] = useState<CaseRow[]>([]);
  const [storage, setStorage] = useState<Storage | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState<number | null>(0);
  const [trashOffset, setTrashOffset] = useState<number | null>(0);
  async function page(deleted: boolean, start: number) {
    const result = await api<{ cases: CaseRow[]; next_offset: number | null }>(
      `/api/cases?deleted=${deleted}&offset=${start}&limit=50`,
    );
    const update = deleted ? setTrash : setRows;
    update((old) => (start ? [...old, ...result.cases] : result.cases));
    (deleted ? setTrashOffset : setOffset)(result.next_offset);
  }
  async function refresh() {
    await Promise.all([page(false, 0), page(true, 0)]);
    if (admin) setStorage(await api<Storage>("/api/admin/storage"));
  }
  useEffect(() => {
    void refresh().catch((e) => setError(String(e)));
  }, []);
  async function action(
    work: () => Promise<unknown>,
    message: string,
    reload = true,
  ) {
    setBusy(true);
    setError("");
    setNotice("");
    setPlan(null);
    setConfirmation("");
    try {
      await work();
      if (reload) await refresh();
      setNotice(message);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function review() {
    setBusy(true);
    setError("");
    setConfirmation("");
    try {
      setPlan(await post<Plan>("/api/retention/plan"));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Files and storage" className="storage-settings">
      <h3>Files and storage</h3>
      <p>
        Move completed or paused cases to Trash to hide them. Restore them at
        any time before permanent deletion.
      </p>
      <ul>
        {rows.map((c) => (
          <li key={c.id}>
            {c.title}{" "}
            <button
              disabled={busy}
              onClick={() =>
                void action(
                  () => post(`/api/cases/${c.id}/trash`),
                  "Case moved to Trash.",
                )
              }
            >
              Move to Trash
            </button>
          </li>
        ))}
      </ul>
      {offset !== null && (
        <button
          disabled={busy}
          onClick={() =>
            void action(() => page(false, offset), "More cases loaded.", false)
          }
        >
          Load more cases
        </button>
      )}
      <h4>Trash</h4>
      {!trash.length && <p>Trash is empty.</p>}
      <ul>
        {trash.map((c) => (
          <li key={c.id}>
            {c.title}{" "}
            <button
              disabled={busy}
              onClick={() =>
                void action(
                  () => post(`/api/cases/${c.id}/restore`),
                  "Case restored.",
                )
              }
            >
              Restore case
            </button>
          </li>
        ))}
      </ul>
      {trashOffset !== null && (
        <button
          disabled={busy}
          onClick={() =>
            void page(true, trashOffset).catch((e) => setError(String(e)))
          }
        >
          Load more Trash
        </button>
      )}
      <button disabled={busy} onClick={() => void review()}>
        Review Trash older than 90 days
      </button>
      {plan && (
        <div className="retention-review">
          <h4>Review permanent deletion</h4>
          <p>
            {plan.cases.length} cases. Approval expires{" "}
            {new Date(plan.expires_at).toLocaleString()}. A verified backup is
            required before deletion.
          </p>
          <ul>
            {plan.cases.map((c) => (
              <li key={c.id}>
                {c.title} · {c.id}
              </li>
            ))}
          </ul>
          <details>
            <summary>Exact deletion plan</summary>
            <pre>{JSON.stringify(plan, null, 2)}</pre>
          </details>
          {plan.cases.length > 0 && (
            <>
              <label htmlFor="retention-confirmation">
                Type {CONFIRM} to approve this plan
              </label>
              <input
                id="retention-confirmation"
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                autoComplete="off"
              />
              <button
                disabled={busy || confirmation !== CONFIRM}
                onClick={() =>
                  void action(
                    () =>
                      post("/api/retention/apply", {
                        plan_id: plan.id,
                        expected_sha256: plan.sha256,
                        confirmation,
                      }),
                    "Reviewed Trash permanently deleted; backup retained.",
                  )
                }
              >
                Approve reviewed deletion
              </button>
            </>
          )}
        </div>
      )}
      {admin && (
        <>
          <h4>Workspace backups</h4>
          <p>
            Backups include all accounts’ case data and password hashes. Keep
            downloaded copies private. Sessions are revoked on restore. The
            service must be idle to create a backup.
          </p>
          {storage?.databases.map((d) => (
            <p key={d.name}>
              {d.name}: {(d.logical_bytes / 1048576).toFixed(1)} /{" "}
              {(d.limit_bytes / 1048576).toFixed(0)} MiB
            </p>
          ))}
          <button
            disabled={busy}
            onClick={() =>
              void action(
                () => post("/api/admin/backups"),
                "Verified workspace backup created.",
              )
            }
          >
            Create verified backup
          </button>
          <ul>
            {storage?.backups.map((b) => (
              <li key={b.id}>
                <a href={`/api/admin/backups/${b.id}/file`}>Download {b.id}</a>{" "}
                · {(b.size / 1048576).toFixed(1)} MiB
                <details>
                  <summary>SHA-256</summary>
                  <code>{b.sha256}</code>
                </details>
              </li>
            ))}
          </ul>
          <p>
            Restore through the local maintenance command into a new state
            directory. See the operator guide. Three backups are retained at
            most; move an older backup to secure offline storage before creating
            another.
          </p>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
