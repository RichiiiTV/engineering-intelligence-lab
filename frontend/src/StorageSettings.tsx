import { useLanguage, t, getLocale } from "./i18n";
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
  useLanguage();
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
    <section
      aria-label={t("Dateien und Speicher")}
      className="storage-settings"
    >
      <h3>{t("Dateien und Speicher")}</h3>
      <p>
        {t(
          "Verschiebe abgeschlossene oder pausierte Fälle zum Ausblenden in den Papierkorb. Vor der endgültigen Löschung kannst du sie jederzeit wiederherstellen.",
        )}
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
                  t("Fall in den Papierkorb verschoben."),
                )
              }
            >
              {t("In den Papierkorb verschieben")}
            </button>
          </li>
        ))}
      </ul>
      {offset !== null && (
        <button
          disabled={busy}
          onClick={() =>
            void action(
              () => page(false, offset),
              t("Weitere Fälle geladen."),
              false,
            )
          }
        >
          {t("Weitere Fälle laden")}
        </button>
      )}
      <h4>{t("Papierkorb")}</h4>
      {!trash.length && <p>{t("Der Papierkorb ist leer.")}</p>}
      <ul>
        {trash.map((c) => (
          <li key={c.id}>
            {c.title}{" "}
            <button
              disabled={busy}
              onClick={() =>
                void action(
                  () => post(`/api/cases/${c.id}/restore`),
                  t("Fall wiederhergestellt."),
                )
              }
            >
              {t("Fall wiederherstellen")}
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
          {t("Weitere Papierkorbeinträge laden")}
        </button>
      )}
      <button disabled={busy} onClick={() => void review()}>
        {t("Papierkorbeinträge älter als 90 Tage prüfen")}
      </button>
      {plan && (
        <div className="retention-review">
          <h4>{t("Endgültige Löschung prüfen")}</h4>
          <p>
            {plan.cases.length} {t("Fälle. Freigabe läuft ab")}{" "}
            {new Date(plan.expires_at).toLocaleString(getLocale())}
            {t(
              ". Vor dem Löschen ist eine verifizierte Sicherung erforderlich.",
            )}
          </p>
          <ul>
            {plan.cases.map((c) => (
              <li key={c.id}>
                {c.title} · {c.id}
              </li>
            ))}
          </ul>
          <details>
            <summary>{t("Genauer Löschplan")}</summary>
            <pre>{JSON.stringify(plan, null, 2)}</pre>
          </details>
          {plan.cases.length > 0 && (
            <>
              <label htmlFor="retention-confirmation">
                {t("Eingabe:")} {CONFIRM} {t("zum Freigeben dieses Plans")}
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
                    t(
                      "Geprüfte Papierkorbeinträge endgültig gelöscht; Sicherung bleibt erhalten.",
                    ),
                  )
                }
              >
                {t("Geprüfte Löschung freigeben")}
              </button>
            </>
          )}
        </div>
      )}
      {admin && (
        <>
          <h4>{t("Sicherungen des Arbeitsbereichs")}</h4>
          <p>
            {t(
              "Sicherungen enthalten die Falldaten und Passwort-Hashes aller Konten. Heruntergeladene Kopien privat aufbewahren. Bei der Wiederherstellung werden Sitzungen widerrufen. Der Dienst muss für eine Sicherung im Leerlauf sein.",
            )}
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
                t("Verifizierte Sicherung des Arbeitsbereichs erstellt."),
              )
            }
          >
            {t("Verifizierte Sicherung erstellen")}
          </button>
          <ul>
            {storage?.backups.map((b) => (
              <li key={b.id}>
                <a href={`/api/admin/backups/${b.id}/file`}>
                  {t("Herunterladen")} {b.id}
                </a>{" "}
                · {(b.size / 1048576).toFixed(1)} MiB
                <details>
                  <summary>SHA-256</summary>
                  <code>{b.sha256}</code>
                </details>
              </li>
            ))}
          </ul>
          <p>
            {t(
              "Die Wiederherstellung erfolgt mit dem lokalen Wartungsbefehl in ein neues Zustandsverzeichnis. Siehe Betriebsanleitung. Es werden höchstens drei Sicherungen aufbewahrt; verschiebe eine ältere Sicherung vor einer weiteren Erstellung in einen sicheren Offline-Speicher.",
            )}
          </p>
        </>
      )}
      {error && <p role="alert">{t(error)}</p>}
      {notice && <p role="status">{t(notice)}</p>}
    </section>
  );
}
