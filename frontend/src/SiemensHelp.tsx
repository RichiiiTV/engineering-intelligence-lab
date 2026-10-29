import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  Beaker,
  BookOpen,
  ExternalLink,
  LoaderCircle,
  Search,
} from "lucide-react";
import { post } from "./api";
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
};

export function siemensUrl(value: string) {
  try {
    if (/[\\\s]/.test(value)) return false;
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      !url.username &&
      !url.password &&
      (!url.port || url.port === "443") &&
      (url.hostname === "siemens.com" ||
        url.hostname.endsWith(".siemens.com")) &&
      url.hostname !== "jobs.siemens.com"
    );
  } catch {
    return false;
  }
}

export default function SiemensHelp() {
  const [question, setQuestion] = useState("");
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
      });
      if (mounted.current) setResult(answer);
    } catch (e) {
      if (mounted.current)
        setError(e instanceof Error ? e.message : "Search failed. Try again.");
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
        <nav aria-label="Main navigation">
          <a href="/">Investigate files</a>
          <a href="/?page=investigations">My investigations</a>
        </nav>
      </header>
      <main className="ux-main">
        <div className="ux-intro">
          <BookOpen size={30} />
          <h1>Siemens SPS / PLC help</h1>
          <p>Find Siemens information for SIMATIC, S7 and TIA Portal.</p>
        </div>
        <form className="siemens-form" onSubmit={(e) => void submit(e)}>
          <label htmlFor="siemens-question">Your SPS / PLC question</label>
          <textarea
            id="siemens-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={500}
            required
            rows={4}
            placeholder="For example: Where is OB1 cycle-time behavior documented for S7-1500?"
          />
          <div className="siemens-examples">
            <button
              type="button"
              onClick={() =>
                setQuestion("SIMATIC S7-1500 OB1 cycle time documentation")
              }
            >
              OB1 cycle time
            </button>
            <button
              type="button"
              onClick={() =>
                setQuestion("TIA Portal S7-1200 programming manual")
              }
            >
              S7-1200 programming
            </button>
          </div>
          <p className="siemens-disclosure">
            Search sends the question above to Siemens’s public MCP service. Use
            public product questions. Case files and investigation history are
            kept separate.
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
            {busy ? "Searching Siemens…" : "Search Siemens"}
          </button>
        </form>
        {error && (
          <div className="ux-error" role="alert">
            {error}
          </div>
        )}
        {busy && <p role="status">Waiting for Siemens documentation search…</p>}
        {result && (
          <section
            className="siemens-results"
            aria-label="Siemens search results"
          >
            <h2>{result.question}</h2>
            {result.connection_verified && (
              <p className="siemens-meta">
                Retrieved from Siemens MCP ·{" "}
                {new Date(result.retrieved_at).toLocaleString()}
              </p>
            )}
            {sources.length > 0 ? (
              <>
                {result.summary && (
                  <div className="siemens-summary">
                    <h3>Siemens-generated search summary</h3>
                    <p>{result.summary}</p>
                  </div>
                )}
                <h3>Sources returned by Siemens</h3>
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
                          ? "Product information"
                          : "Documentation / web content"}
                      </small>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <p>
                No eligible Siemens sources were returned. Try a shorter
                question with the CPU family, firmware or TIA Portal version.
              </p>
            )}
            <p className="siemens-disclosure">{result.limitations}</p>
          </section>
        )}
        <footer className="ux-footer">
          <a href="/?view=advanced">Advanced workspace</a>
        </footer>
      </main>
    </div>
  );
}
