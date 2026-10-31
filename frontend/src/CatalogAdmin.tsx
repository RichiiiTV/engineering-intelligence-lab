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
      setError(
        "Bestätige die Berechtigung zur Freigabe dieser Dateien im Arbeitsbereich.",
      );
      return;
    }
    if (!files.length || files.length > 4) {
      setError("Pro Stapel eine bis vier Quelldateien auswählen.");
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
        `${accepted} Datei${accepted === 1 ? "" : "s"} eingereiht. Das System extrahiert und indexiert die Inhalte und ordnet sie automatisch einer Maschine zu.`,
      );
    });
    if (accepted && accepted < files.length) {
      setChosen(files.slice(accepted));
      setNotice(
        `${accepted} Dateien angenommen. Warte vor dem Hochladen weiterer Dateien die Indexierung ab; angenommene Dateien bleiben unter Upload-Aktivitäten sichtbar.`,
      );
    }
  }
  return (
    <section aria-label="Maschinenwissen verwalten">
      <h2>Maschinenwissen</h2>
      <p>
        Handbücher, Dokumentation und Code-Exporte hinzufügen. Das System liest
        die Dateien, erstellt lokale Embeddings und ordnet sie automatisch dem
        Maschinenwissen zu.
      </p>
      <form className="machine-card machine-form" onSubmit={upload}>
        <h3>
          <Upload size={19} />
          Maschinendaten hinzufügen
        </h3>
        <label>
          Quelldateien
          <input
            name="files"
            aria-label="Maschinen-Quelldateien"
            type="file"
            multiple
            onChange={(e) => setChosen(Array.from(e.target.files || []))}
            accept=".pdf,.md,.txt,.st,.scl,.awl,.py,.js,.ts,.c,.cpp,.h,.xml,.json,.yaml,.yml,.cfg,.ini,.csv"
          />
        </label>
        {chosen.length > 0 && (
          <p className="ux-small">
            Vorgemerkte Dateien: {chosen.map((f) => f.name).join(", ")}
          </p>
        )}
        <p className="ux-small">
          Bis zu vier Dateien pro Stapel. Keine Maschinenbenennung oder
          Quellenauswahl erforderlich. Nach der Verarbeitung stehen die Dateien
          angemeldeten Benutzern dieses Arbeitsbereichs zur Verfügung.
        </p>
        <label className="machine-check">
          <input name="authorized" type="checkbox" required />
          Ich bin berechtigt, diese Dateien für Benutzer dieses Arbeitsbereichs
          freizugeben.
        </label>
        <button className="ux-primary" disabled={busy}>
          {busy ? <LoaderCircle size={17} /> : <Upload size={17} />}Hochladen
          und automatisch zuordnen
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
          <h3>Upload-Aktivitäten</h3>
          {jobs.slice(0, 15).map((j) => (
            <div className="machine-source" key={j.id}>
              <strong>{j.filename}</strong>
              <small>
                {j.status === "completed"
                  ? "Bereit"
                  : j.phase === "classifying"
                    ? "Maschine wird erkannt…"
                    : statusLabel(j.phase)}{" "}
                · {j.progress}%
                {j.classifier_calls
                  ? ` · Zuordnungsversuche ${j.classifier_calls}/3`
                  : ""}
              </small>
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
                    {terminal.has(j.status) ? "Erneut versuchen" : "Abbrechen"}
                  </button>
                  {terminal.has(j.status) && (
                    <details>
                      <summary>Zwischengespeicherten Upload verwerfen</summary>
                      <p>
                        Nur die zwischengespeicherten Upload-Daten verwerfen.
                        Danach kann dieser Auftrag nicht erneut gestartet
                        werden. Veröffentlichte Quellen und Antworten bleiben
                        erhalten.
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
                        Verwerfen bestätigen
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
        Automatisch zugeordnetes Wissen
      </h3>
      {!machines.length && (
        <p className="ux-small">
          Lade Dateien hoch, um das Maschinenwissen aufzubauen. Bestehende
          private Arbeitsbereiche bleiben getrennt.
        </p>
      )}
      <div className="machine-groups">
        {machines.map((m) => (
          <section className="machine-card" key={m.id}>
            <span className="machine-eyebrow">
              {m.identity_kind === "unknown"
                ? "IDENTITÄT NICHT BELEGT"
                : m.identity_kind === "product_family"
                  ? "PRODUKTFAMILIE"
                  : "MASCHINENWISSEN"}
            </span>
            <h2>{m.name}</h2>
            {m.identity_kind === "unknown" && (
              <p className="ux-caution">
                Keine belegte Maschinenkennung gefunden. Der Chat fragt nach,
                anstatt eine Maschine anzunehmen.
              </p>
            )}
            {m.documents.map((d) => (
              <details className="machine-source" key={d.id}>
                <summary>
                  <FileText size={14} /> {d.filename} ·{" "}
                  {d.active ? "Verfügbar" : "Archiviert"}
                </summary>
                <p className="ux-small">
                  Zuordnung:{" "}
                  {d.assignment_basis === "semantic-inference"
                    ? "Schlussfolgerung aus Embeddings und LLM"
                    : d.assignment_basis === "source-identity"
                      ? "Kennung in der Quelle gefunden"
                      : "Nicht zugeordnet"}{" "}
                  ·{" "}
                  {(
                    {
                      high: "hohe",
                      medium: "mittlere",
                      low: "niedrige",
                    } as Record<string, string>
                  )[d.classification?.confidence || ""] || "unbekannte"}{" "}
                  Extraktionskonfidenz
                </p>
                {d.classification?.identity_evidence && (
                  <blockquote>{d.classification.identity_evidence}</blockquote>
                )}
                <div className="machine-actions">
                  <a
                    href={`/api/admin/machine-knowledge/documents/${d.id}/file`}
                  >
                    Original herunterladen
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
                      ? "Für zukünftige Antworten archivieren"
                      : "Aktivieren"}
                  </button>
                </div>
              </details>
            ))}
          </section>
        ))}
      </div>
      <p className="ux-small">
        Benutzer beschreiben nur ihr Problem und fügen bei Bedarf Bilder oder
        Protokolle hinzu. Das System übernimmt Maschinenzuordnung, Quellensuche
        und Gesprächskontext. Chats und Anhänge werden nicht in dieses
        gemeinsame Wissen aufgenommen.
      </p>
    </section>
  );
}
