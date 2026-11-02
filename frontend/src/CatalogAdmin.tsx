import { useLanguage, t, tr } from "./i18n";
import { useEffect, useState, type FormEvent } from "react";
import { Upload, FileText, FolderCheck, LoaderCircle } from "lucide-react";
import { api, post } from "./api";
import { statusLabel, requestError } from "./locale";
import "./machines.css";
type Source = {
  id: string;
  filename: string;
  active: boolean;
  assignment_basis: string;
  passages?: number;
  indexed_passages?: number;
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
  document_id?: string;
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
  useLanguage();
  const [machines, setMachines] = useState<Machine[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [error, setError] = useState(""),
    [loadError, setLoadError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [chosen, setChosen] = useState<File[]>([]);
  const [dataPolicy, setDataPolicy] = useState<"internal" | "licensed-public">(
    "internal",
  );
  const [licenseNote, setLicenseNote] = useState("");
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
      setError(
        t(
          "Bestätige die Berechtigung zur Freigabe dieser Dateien im Arbeitsbereich.",
        ),
      );
      return;
    }
    if (!files.length || files.length > 4) {
      setError(t("Pro Stapel eine bis vier Quelldateien auswählen."));
      return;
    }
    let accepted = 0;
    await action(async () => {
      for (const file of files) {
        const body = new FormData();
        body.set("file", file);
        body.set("authorized", "true");
        body.set("data_policy", dataPolicy);
        if (licenseNote.trim()) body.set("license_note", licenseNote.trim());
        await api("/api/admin/machine-knowledge/uploads", {
          method: "POST",
          body,
        });
        accepted++;
      }
      form.reset();
      setChosen([]);
      setDataPolicy("internal");
      setLicenseNote("");
      setNotice(
        tr`${accepted} Datei${accepted === 1 ? "" : "s"} eingereiht. Das System extrahiert und indexiert die Inhalte und ordnet sie automatisch einer Maschine zu.`,
      );
    });
    if (accepted && accepted < files.length) {
      setChosen(files.slice(accepted));
      setNotice(
        tr`${accepted} Dateien angenommen. Warte vor dem Hochladen weiterer Dateien die Indexierung ab; angenommene Dateien bleiben unter Upload-Aktivitäten sichtbar.`,
      );
    }
  }
  return (
    <section aria-label={t("Maschinenwissen verwalten")}>
      <h2>{t("Maschinenwissen")}</h2>
      <p>
        {t(
          "Handbücher, Dokumentation und Code-Exporte hinzufügen. Das System liest die Dateien, erstellt lokale Embeddings und ordnet sie automatisch dem Maschinenwissen zu.",
        )}
      </p>
      <form className="machine-card machine-form" onSubmit={upload}>
        <h3>
          <Upload size={19} />
          {t("Maschinendaten hinzufügen")}
        </h3>
        <label>
          {t("Quelldateien")}
          <input
            name="files"
            aria-label={t("Maschinen-Quelldateien")}
            type="file"
            multiple
            onChange={(e) => setChosen(Array.from(e.target.files || []))}
            accept=".pdf,.md,.txt,.st,.scl,.awl,.py,.js,.ts,.c,.cpp,.h,.xml,.json,.yaml,.yml,.cfg,.ini,.csv"
          />
        </label>
        {chosen.length > 0 && (
          <p className="ux-small">
            {t("Vorgemerkte Dateien:")} {chosen.map((f) => f.name).join(", ")}
          </p>
        )}
        <label>
          {t("Inhaltstyp")}
          <select
            value={dataPolicy}
            onChange={(e) =>
              setDataPolicy(e.target.value as "internal" | "licensed-public")
            }
          >
            <option value="internal">{t("Interne Maschinendaten")}</option>
            <option value="licensed-public">
              {t("Lizenzierte öffentliche Dokumentation")}
            </option>
          </select>
        </label>
        {dataPolicy === "licensed-public" && (
          <label>
            {t("Lizenz und Herkunft")}
            <input
              value={licenseNote}
              onChange={(e) => setLicenseNote(e.target.value)}
              maxLength={1000}
              required
              placeholder={t("Lizenz, Urheber und Originalquelle angeben")}
            />
          </label>
        )}
        <p className="ux-small">
          {t(
            "Bis zu vier Dateien pro Stapel. Keine Maschinenbenennung oder Quellenauswahl erforderlich. Nach der Verarbeitung stehen die Dateien angemeldeten Benutzern dieses Arbeitsbereichs zur Verfügung.",
          )}
        </p>
        <label className="machine-check">
          <input name="authorized" type="checkbox" required />
          {t(
            "Ich bin berechtigt, diese Dateien für Benutzer dieses Arbeitsbereichs freizugeben.",
          )}
        </label>
        <button className="ux-primary" disabled={busy}>
          {busy ? <LoaderCircle size={17} /> : <Upload size={17} />}
          {t("Hochladen und automatisch zuordnen")}
        </button>
      </form>
      {(error || loadError) && (
        <p className="ux-error" role="alert">
          {t(error || loadError)}
        </p>
      )}
      {notice && <p role="status">{t(notice)}</p>}
      {jobs.length > 0 && (
        <section className="machine-card">
          <h3>{t("Upload-Aktivitäten")}</h3>
          <p className="ux-small" aria-label={t("Upload-Übersicht")}>
            {t("Abgeschlossen:")}{" "}
            {jobs.filter((j) => j.status === "completed").length}
            {" · "}
            {t("In Arbeit:")}{" "}
            {jobs.filter((j) => !terminal.has(j.status)).length}
            {" · "}
            {t("Aufmerksamkeit nötig:")}{" "}
            {
              jobs.filter(
                (j) =>
                  terminal.has(j.status) &&
                  j.status !== "completed" &&
                  j.phase !== "discarded",
              ).length
            }
          </p>
          {jobs.slice(0, 15).map((j) => (
            <div className="machine-source" key={j.id}>
              <strong>{j.filename}</strong>
              <small>
                {j.status === "completed"
                  ? t("Verarbeitung abgeschlossen")
                  : j.phase === "classifying"
                    ? t("Maschine wird erkannt…")
                    : statusLabel(j.phase)}{" "}
                · {j.progress}%
                {j.classifier_calls
                  ? tr` · Zuordnungsversuche ${j.classifier_calls}/3`
                  : ""}
              </small>
              {j.status === "completed" &&
                (() => {
                  const machine = machines.find(
                    (m) => m.id === j.assigned_machine_id,
                  );
                  const source = machine?.documents.find(
                    (d) => d.id === j.document_id,
                  );
                  if (!machine || !source)
                    return (
                      <p className="ux-small">
                        {t("Zuordnungsergebnis wird geladen…")}
                      </p>
                    );
                  return (
                    <p
                      className={
                        machine.identity_kind === "unknown"
                          ? "ux-caution"
                          : "ux-small"
                      }
                    >
                      {machine.identity_kind === "unknown"
                        ? t("Identität nicht belegt:")
                        : machine.identity_kind === "product_family"
                          ? t("Produktfamilie:")
                          : t("Maschine:")}{" "}
                      <strong>{machine.name}</strong>
                      {" · "}
                      {source.indexed_passages ?? 0}/{source.passages ?? 0}{" "}
                      {t("Abschnitte indexiert")}
                      {" · "}
                      {source.active ? t("Verfügbar") : t("Archiviert")}
                      {source.active &&
                        (source.indexed_passages ?? 0) <
                          (source.passages ?? 0) && (
                          <> · {t("Semantische Indexierung unvollständig")}</>
                        )}
                    </p>
                  );
                })()}
              {!terminal.has(j.status) && (
                <progress value={j.progress} max={100} />
              )}{" "}
              {j.error && (
                <p className="ux-caution">{requestError(j.error, 400)}</p>
              )}{" "}
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
                    {terminal.has(j.status)
                      ? t("Erneut versuchen")
                      : t("Abbrechen")}
                  </button>
                  {terminal.has(j.status) && (
                    <details>
                      <summary>
                        {t("Zwischengespeicherten Upload verwerfen")}
                      </summary>
                      <p>
                        {t(
                          "Nur die zwischengespeicherten Upload-Daten verwerfen. Danach kann dieser Auftrag nicht erneut gestartet werden. Veröffentlichte Quellen und Antworten bleiben erhalten.",
                        )}
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
                        {t("Verwerfen bestätigen")}
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
        {t("Automatisch zugeordnetes Wissen")}
      </h3>
      {!machines.length && (
        <p className="ux-small">
          {t(
            "Lade Dateien hoch, um das Maschinenwissen aufzubauen. Bestehende private Arbeitsbereiche bleiben getrennt.",
          )}
        </p>
      )}
      <div className="machine-groups">
        {machines.map((m) => (
          <section className="machine-card" key={m.id}>
            <span className="machine-eyebrow">
              {m.identity_kind === "unknown"
                ? t("IDENTITÄT NICHT BELEGT")
                : m.identity_kind === "product_family"
                  ? t("PRODUKTFAMILIE")
                  : t("MASCHINENWISSEN")}
            </span>
            <h2>{m.name}</h2>
            {m.identity_kind === "unknown" && (
              <p className="ux-caution">
                {t(
                  "Keine belegte Maschinenkennung gefunden. Der Chat fragt nach, anstatt eine Maschine anzunehmen.",
                )}
              </p>
            )}
            {m.documents.map((d) => (
              <details className="machine-source" key={d.id}>
                <summary>
                  <FileText size={14} /> {d.filename} ·{" "}
                  {d.active ? t("Verfügbar") : t("Archiviert")}
                </summary>
                <p className="ux-small">
                  {d.indexed_passages ?? 0}/{d.passages ?? 0}{" "}
                  {t("Abschnitte indexiert")} · {t("Zuordnung:")}{" "}
                  {d.assignment_basis === "semantic-inference"
                    ? t("Schlussfolgerung aus Embeddings und LLM")
                    : d.assignment_basis === "source-identity"
                      ? t("Kennung in der Quelle gefunden")
                      : t("Nicht zugeordnet")}{" "}
                  ·{" "}
                  {(
                    {
                      high: t("hohe"),
                      medium: t("mittlere"),
                      low: t("niedrige"),
                    } as Record<string, string>
                  )[d.classification?.confidence || ""] || t("unbekannte")}{" "}
                  {t("Extraktionskonfidenz")}
                </p>
                {d.classification?.identity_evidence && (
                  <blockquote>{d.classification.identity_evidence}</blockquote>
                )}
                <div className="machine-actions">
                  <a
                    href={`/api/admin/machine-knowledge/documents/${d.id}/file`}
                  >
                    {t("Original herunterladen")}
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
                    {d.active
                      ? t("Für zukünftige Antworten archivieren")
                      : t("Aktivieren")}
                  </button>
                </div>
              </details>
            ))}
          </section>
        ))}
      </div>
      <p className="ux-small">
        {t(
          "Benutzer beschreiben nur ihr Problem und fügen bei Bedarf Bilder oder Protokolle hinzu. Das System übernimmt Maschinenzuordnung, Quellensuche und Gesprächskontext. Chats und Anhänge werden nicht in dieses gemeinsame Wissen aufgenommen.",
        )}
      </p>
    </section>
  );
}
