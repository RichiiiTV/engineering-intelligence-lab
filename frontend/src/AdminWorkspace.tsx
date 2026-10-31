import { useLanguage, t, getLocale } from "./i18n";
import { useEffect, useState, type FormEvent } from "react";
import { api, post } from "./api";
import type { LibraryDocument } from "./KnowledgeLibrary";
import CatalogAdmin from "./CatalogAdmin";

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
  delivery?: { pending: number; overflow_events: number; healthy: boolean };
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
  useLanguage();
  const [tab, setTab] = useState("catalog");
  return (
    <div className="user-app">
      <main className="ux-main admin-main">
        <button className="ux-link" onClick={onClose}>
          {t("← Zurück zu den Fragen")}
        </button>
        <h1>{t("Arbeitsbereich verwalten")}</h1>
        <nav aria-label="Administration">
          <button
            aria-pressed={tab === "catalog"}
            onClick={() => setTab("catalog")}
          >
            {t("Maschinenwissen")}
          </button>
          <button
            aria-pressed={tab === "documents"}
            onClick={() => setTab("documents")}
          >
            {t("Öffentliche Referenzen")}
          </button>
          <button
            aria-pressed={tab === "users"}
            onClick={() => setTab("users")}
          >
            {t("Benutzer")}
          </button>
          <button
            aria-pressed={tab === "audit"}
            onClick={() => setTab("audit")}
          >
            {t("Audit-Protokoll")}
          </button>
        </nav>
        {tab === "catalog" ? (
          <CatalogAdmin />
        ) : tab === "documents" ? (
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
  useLanguage();
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
      t("Dokument hinzugefügt. Für die semantische Suche bitte indexieren."),
    );
  }
  return (
    <section aria-label={t("Dokumentverwaltung")}>
      <h2>{t("Wissensdokumente")}</h2>
      <p>
        {t(
          "Aktive Dokumente stehen allen Benutzern dieses Arbeitsbereichs zur Verfügung. Jede Frage behält ihren eigenen Dokumentstand. Neue Versionen werden als neues Dokument hinzugefügt; die alte Version kann deaktiviert werden.",
        )}
      </p>
      <div className="admin-list">
        {rows.map((d) => (
          <article key={d.id}>
            <h3>{d.title}</h3>
            <p>
              {d.family} · {d.version} ·{" "}
              {d.active ? t("Aktiv") : t("Deaktiviert")}
            </p>
            <p className="ux-small">{d.license_note}</p>
            <p>
              {d.indexed_passages}/{d.passages}{" "}
              {t("Abschnitte für die semantische Suche indexiert")}
            </p>
            <div className="admin-actions">
              <a href={`/api/library/documents/${d.id}/file`}>
                {t("Herunterladen")}
              </a>
              <button
                disabled={busy || !d.active}
                onClick={() =>
                  void action(
                    () => post(`/api/library/documents/${d.id}/index`),
                    t("Semantischer Index gespeichert."),
                  )
                }
              >
                {t("Dokument indexieren")}
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
                      ? t("Dokument für neue Fragen deaktiviert.")
                      : t("Dokument aktiviert."),
                  )
                }
              >
                {d.active ? t("Deaktivieren") : t("Aktivieren")}
              </button>
            </div>
          </article>
        ))}
      </div>
      <details className="admin-add">
        <summary>{t("Gemeinsames Dokument hinzufügen")}</summary>
        <form onSubmit={(e) => void upload(e)} className="siemens-form">
          <label>
            {t("Dokumenttitel")}
            <input name="title" required maxLength={160} />
          </label>
          <label>
            {t("Produktfamilie")}
            <input
              name="family"
              required
              maxLength={60}
              placeholder={t("Zum Beispiel SIMATIC S7-1500")}
            />
          </label>
          <label>
            {t("Version / Handbuchausgabe")}
            <input name="version" required maxLength={80} />
          </label>
          <label>
            {t("Lizenz und Herkunft")}
            <input
              name="license_note"
              required
              maxLength={300}
              placeholder={t("Lizenz für Nutzung und Weitergabe angeben")}
            />
          </label>
          <label>
            {t("Inhaltstyp")}
            <select name="data_policy">
              <option value="synthetic">
                {t("Generiertes Demonstrationsmaterial")}
              </option>
              <option value="licensed-public">
                {t("Ausdrücklich lizenziertes öffentliches Material")}
              </option>
            </select>
          </label>
          <label>
            {t("Quelldatei")}
            <input type="file" name="file" accept=".pdf,.md,.txt" required />
          </label>
          <p className="ux-small">
            {t(
              "PDF: bis 10 MiB / 20 Seiten. UTF-8-Text oder Markdown: bis 1 MiB. Keine OCR. Seitenzahlen in Textdateien folgen den Seitenumbruchzeichen.",
            )}
          </p>
          <label className="ux-confirm">
            <input type="checkbox" name="confirmed" value="true" required />
            <span>
              {t(
                "Ich bestätige, dass die Lizenz die Freigabe für alle Benutzer dieses Arbeitsbereichs erlaubt.",
              )}
            </span>
          </label>
          <button className="ux-primary" disabled={busy}>
            {t("Dokument hinzufügen")}
          </button>
        </form>
      </details>
      {busy && <p role="status">{t("Lokale Verarbeitung…")}</p>}
      {error && <p role="alert">{t(error)}</p>}
      {notice && <p role="status">{t(notice)}</p>}
    </section>
  );
}

function Users({ currentUserId }: { currentUserId: string }) {
  useLanguage();
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
      return true;
    } catch (e) {
      setError(String(e));
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fields = new FormData(form);
    const success = await action(
      () => post("/api/auth/users", Object.fromEntries(fields)),
      t("Benutzerkonto erstellt."),
    );
    if (success) form.reset();
  }
  return (
    <section aria-label={t("Benutzerverwaltung")}>
      <h2>{t("Benutzer des Arbeitsbereichs")}</h2>
      <p>
        {t(
          "Mitglieder sehen ihre eigenen Untersuchungen und die gemeinsame Bibliothek. Administratoren verwalten zusätzlich Benutzer, Dokumente, Speicher und Audit-Protokolle.",
        )}
      </p>
      <div className="admin-list">
        {rows.map((u) => (
          <article key={u.id}>
            <h3>
              {u.username}
              {u.id === currentUserId ? " (you)" : ""}
            </h3>
            <p>
              {u.role} · {u.active ? t("Aktiv") : t("Deaktiviert")} ·{" "}
              {u.sessions} {t("aktive Sitzungen")}
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
                    t("Rolle aktualisiert; bestehende Sitzungen widerrufen."),
                  )
                }
              >
                {u.role === "admin"
                  ? t("Als Mitglied festlegen")
                  : t("Als Administrator festlegen")}
              </button>
              <button
                disabled={busy || u.id === currentUserId}
                onClick={() =>
                  void action(
                    () =>
                      post(`/api/auth/users/${u.id}/update`, {
                        active: !u.active,
                      }),
                    t(
                      "Kontoverfügbarkeit aktualisiert; Sitzungen deaktivierter Konten widerrufen.",
                    ),
                  )
                }
              >
                {u.active ? t("Konto deaktivieren") : t("Konto aktivieren")}
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  void action(
                    () => post(`/api/auth/users/${u.id}/revoke-sessions`),
                    t("Sitzungen widerrufen."),
                  )
                }
              >
                {t("Alle Sitzungen abmelden")}
              </button>
            </div>
          </article>
        ))}
      </div>
      {next !== null && (
        <button disabled={busy} onClick={() => void refresh(next)}>
          {t("Weitere Benutzer laden")}
        </button>
      )}
      <details className="admin-add">
        <summary>{t("Benutzer anlegen")}</summary>
        <form className="siemens-form" onSubmit={(e) => void create(e)}>
          <label>
            {t("Benutzername")}
            <input
              name="username"
              minLength={3}
              maxLength={40}
              required
              autoComplete="off"
            />
          </label>
          <label>
            {t("Anfangspasswort")}
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
            {t("Rolle")}
            <select name="role">
              <option value="member">{t("Mitglied")}</option>
              <option value="admin">Administrator</option>
            </select>
          </label>
          <button disabled={busy}>{t("Konto erstellen")}</button>
        </form>
      </details>
      {error && <p role="alert">{t(error)}</p>}
      {notice && <p role="status">{t(notice)}</p>}
    </section>
  );
}

function Audit() {
  useLanguage();
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
    <section aria-label={t("Audit-Protokoll des Arbeitsbereichs")}>
      <h2>{t("Audit-Protokoll")}</h2>
      <p>
        {t(
          "Erfasst Anmeldungen, Kontoänderungen, Dokumentverwaltung, Änderungen, Downloads und verweigerte Zugriffe. Fragen, Dokumentinhalte, Passwörter und Sitzungstoken werden nicht protokolliert.",
        )}
      </p>
      <form
        className="admin-filters"
        onSubmit={(e) => {
          e.preventDefault();
          void refresh();
        }}
      >
        <label>
          {t("Ereignistyp")}
          <input
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            placeholder={t("Zum Beispiel user_updated")}
          />
        </label>
        <label>
          {t("Akteur-ID")}
          <input
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            maxLength={40}
          />
        </label>
        <button>{t("Filter anwenden")}</button>
      </form>
      {page && (
        <p role="status">
          {page.integrity.valid
            ? t("Audit-Kette verifiziert")
            : t("Audit-Integritätsprüfung fehlgeschlagen")}{" "}
          · {page.integrity.checked} {t("Ereignisse geprüft")}
        </p>
      )}
      <p className="ux-small">
        {t(
          "Die Anwendung fügt Einträge nur an. Ein lokaler Datenbankadministrator kann die Datenbank ersetzen; exportierte Prüfsummen sollten unabhängig aufbewahrt werden.",
        )}
      </p>
      <a href="/api/admin/audit/export">
        {t("Erste Audit-Seite herunterladen (JSON, bis 100 Ereignisse)")}
      </a>
      <p>
        <a href="/api/admin/audit/complete">
          {t("Vollständiges Audit-Protokoll herunterladen (JSONL)")}
        </a>
      </p>
      <button
        onClick={() =>
          void post("/api/admin/audit/archive")
            .then(() => refresh())
            .catch((e) => setError(String(e)))
        }
      >
        {t("Aktuelles Segment archivieren (Verlauf bleibt erhalten)")}
      </button>
      {page?.delivery &&
        (!page.delivery.healthy || page.delivery.pending > 0) && (
          <p role="alert">
            {t("Audit-Zustellung benötigt Aufmerksamkeit:")}{" "}
            {page.delivery.pending} {t("ausstehende Ereignisse;")}{" "}
            {page.delivery.overflow_events}{" "}
            {t(
              "zusammengefasste Überlaufereignisse. Die Anmeldung bleibt verfügbar.",
            )}
          </p>
        )}
      <div className="admin-audit">
        {events.map((e) => (
          <article key={e.id}>
            <strong>
              #{e.id} {e.kind}
            </strong>
            <small>
              {new Date(e.at * 1000).toLocaleString(getLocale())} ·{" "}
              {e.actor || e.actor_id || t("Nicht authentifiziert")}
            </small>
            <p>{e.subject_id}</p>
            <details>
              <summary>
                {t("Ereignismetadaten und Integritätsprüfsumme")}
              </summary>
              <pre>{JSON.stringify(e.details, null, 2)}</pre>
              <code>{e.entry_hash}</code>
            </details>
          </article>
        ))}
      </div>
      {page?.next_after != null && (
        <button onClick={() => void refresh(page.next_after!)}>
          {t("Weitere Audit-Ereignisse laden")}
        </button>
      )}
      {error && <p role="alert">{t(error)}</p>}
    </section>
  );
}
