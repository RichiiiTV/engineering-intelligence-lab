import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  Beaker,
  BookOpen,
  ExternalLink,
  LoaderCircle,
  Search,
} from "lucide-react";
import { post } from "./api";
import { siemensUrl } from "./siemens";
export { siemensUrl } from "./siemens";
import "./user.css";

type Source = { title: string; url: string; description: string; kind: string };
type SearchResult = {
  question: string;
  summary: string;
  sources: Source[];
  retrieved_at: string;
  server_version: string;
  connection_verified: boolean;
  limitations: string;
  curated_references?: (Source & {
    tia_version: string;
    edition: string;
    language: string;
  })[];
  version_notice?: string;
  outbound_query?: string;
};

export default function SiemensHelp() {
  const [question, setQuestion] = useState("");
  const [family, setFamily] = useState("");
  const [cpu, setCpu] = useState("");
  const [firmware, setFirmware] = useState("");
  const [tia, setTia] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !question.trim()) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const answer = await post<SearchResult>("/api/knowledge/siemens/search", {
        question: question.trim(),
        ...(family ? { family } : {}),
        ...(cpu ? { cpu } : {}),
        ...(firmware ? { firmware } : {}),
        ...(tia ? { tia_version: tia } : {}),
      });
      if (mounted.current) setResult(answer);
    } catch (e) {
      if (mounted.current)
        setError(
          e instanceof Error
            ? e.message
            : "Suche fehlgeschlagen. Bitte erneut versuchen.",
        );
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  const sources =
    result?.sources.filter((source) => siemensUrl(source.url)).slice(0, 8) ||
    [];
  return (
    <div className="user-app siemens-help">
      <header className="ux-header">
        <a className="ux-brand" href="/">
          <Beaker size={29} />
          <span>Engineering Intelligence Lab</span>
        </a>
        <nav aria-label="Hauptnavigation">
          <a href="/">Dateien untersuchen</a>
          <a href="/?page=investigations">Meine Untersuchungen</a>
        </nav>
      </header>
      <main className="ux-main">
        <div className="ux-intro">
          <BookOpen size={30} />
          <h1>Siemens SPS-Hilfe</h1>
          <p>Siemens-Informationen zu SIMATIC, S7 und TIA Portal finden.</p>
        </div>
        <form className="siemens-form" onSubmit={(e) => void submit(e)}>
          <label htmlFor="siemens-question">Deine SPS-Frage</label>
          <textarea
            id="siemens-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={500}
            required
            rows={4}
            placeholder="Zum Beispiel: Wo ist das OB1-Zykluszeitverhalten der S7-1500 dokumentiert?"
          />
          <div className="siemens-examples">
            <button
              type="button"
              onClick={() =>
                setQuestion("SIMATIC S7-1500 OB1 Zykluszeit Dokumentation")
              }
            >
              OB1-Zykluszeit
            </button>
            <button
              type="button"
              onClick={() =>
                setQuestion("TIA Portal S7-1200 Programmierhandbuch")
              }
            >
              S7-1200-Programmierung
            </button>
          </div>
          <details>
            <summary>Produkt und Version (optional)</summary>
            <label htmlFor="siemens-family">SIMATIC-Familie</label>
            <select
              id="siemens-family"
              value={family}
              onChange={(e) => setFamily(e.target.value)}
            >
              <option value="">Nicht angegeben</option>
              {["S7-1200", "S7-1200 G2", "S7-1500"].map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
            <label htmlFor="siemens-cpu">
              Öffentliches CPU-Modell oder Bestellnummer
            </label>
            <input
              id="siemens-cpu"
              value={cpu}
              onChange={(e) => setCpu(e.target.value)}
              maxLength={50}
            />
            <label htmlFor="siemens-firmware">Firmware-Version</label>
            <input
              id="siemens-firmware"
              value={firmware}
              onChange={(e) => setFirmware(e.target.value)}
              maxLength={12}
              placeholder="V3.1"
            />
            <label htmlFor="siemens-tia">TIA-Portal-Version</label>
            <select
              id="siemens-tia"
              value={tia}
              onChange={(e) => setTia(e.target.value)}
            >
              <option value="">Nicht angegeben</option>
              {[17, 18, 19, 20, 21].map((v) => (
                <option key={v}>V{v}</option>
              ))}
            </select>
            <p>
              Diese Felder werden mit deiner Frage gesendet. Die gesamte
              Suchanfrage ist auf 500 Zeichen begrenzt.
            </p>
          </details>
          <p className="siemens-disclosure">
            Die Suche sendet die obige Frage und den ausgewählten Produktkontext
            an den öffentlichen MCP-Dienst von Siemens. Verwende öffentliche
            Produktfragen. Falldateien und Untersuchungsverlauf bleiben
            getrennt.
          </p>
          <button
            className="ux-primary"
            disabled={busy || !question.trim()}
            type="submit"
          >
            {busy ? (
              <LoaderCircle size={18} className="spin" />
            ) : (
              <Search size={18} />
            )}
            {busy ? "Siemens wird durchsucht…" : "Siemens durchsuchen"}
          </button>
        </form>
        {error && (
          <div className="ux-error" role="alert">
            {error}
          </div>
        )}
        {busy && (
          <p role="status">Wartet auf die Siemens-Dokumentationssuche…</p>
        )}
        {result && (
          <section
            className="siemens-results"
            aria-label="Siemens-Suchergebnisse"
          >
            <h2>{result.question}</h2>
            {result.version_notice && <p>{result.version_notice}</p>}
            {(result.curated_references?.length || 0) > 0 && (
              <section aria-label="Geprüfte Handbuchkandidaten">
                <h3>Geprüfte Handbuchkandidaten</h3>
                {result
                  .curated_references!.filter((s) => siemensUrl(s.url))
                  .map((s) => (
                    <p key={s.url}>
                      <a href={s.url} target="_blank" rel="noopener noreferrer">
                        {s.title}
                      </a>
                      <br />
                      {s.tia_version} · {s.edition} · {s.language} · Gültigkeit
                      für genaue CPU und Firmware prüfen
                    </p>
                  ))}
              </section>
            )}
            {result.outbound_query && (
              <details>
                <summary>Exakt übermittelte Suchanfrage</summary>
                <pre>{result.outbound_query}</pre>
              </details>
            )}
            {result.connection_verified && (
              <p className="siemens-meta">
                Von Siemens MCP abgerufen ·{" "}
                {new Date(result.retrieved_at).toLocaleString("de-DE")}
              </p>
            )}
            {sources.length > 0 ? (
              <>
                {result.summary && (
                  <div className="siemens-summary">
                    <h3>Von Siemens generierte Suchzusammenfassung</h3>
                    <p>{result.summary}</p>
                  </div>
                )}
                <h3>Von Siemens zurückgegebene Quellen</h3>
                <div className="siemens-sources">
                  {sources.map((source) => (
                    <article key={source.url}>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {source.title}
                        <ExternalLink size={14} />
                      </a>
                      <p>{source.description}</p>
                      <small>
                        {new URL(source.url).hostname} ·{" "}
                        {source.kind === "product"
                          ? "Produktinformationen"
                          : "Dokumentation / Webinhalte"}
                      </small>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <p>
                Keine zulässigen Siemens-Quellen zurückgegeben. Versuche eine
                kürzere Frage mit CPU-Familie, Firmware oder TIA-Portal-Version.
              </p>
            )}
            <p className="siemens-disclosure">{result.limitations}</p>
          </section>
        )}
        <footer className="ux-footer">
          <a href="/?view=advanced">Erweiterter Arbeitsbereich</a>
        </footer>
      </main>
    </div>
  );
}
