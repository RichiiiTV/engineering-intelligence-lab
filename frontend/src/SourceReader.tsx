import {
  Fragment,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ArrowUpRight, Download, FileText, X } from "lucide-react";
import { t, useLanguage } from "./i18n";
import type { EvidenceReport } from "./types";
import "./sourceReader.css";

export type LocalSource =
  | NonNullable<EvidenceReport["library_citations"]>[number]
  | NonNullable<EvidenceReport["problem_citations"]>[number];

// Pack wrappers are presentation metadata only. The complete, unchanged passage
// always remains available in Original excerpt; nothing is executed or fetched.
function passage(source: LocalSource) {
  const text = source.text;
  const boundary = /^## Upstream source: (.+)\r?$/m.exec(text);
  const wrapper =
    boundary &&
    /^## Upstream source: [^\n]+\r?\n\r?\nOriginal source: https:\/\/github\.com\/[^\n]+\r?\n\r?\nCommit: [a-f0-9]{40}\r?\n\r?\nSHA-256 of original bytes: [a-f0-9]{64}\r?\n\r?\n`{6}text\r?\n/.exec(
      text.slice(boundary.index),
    );
  let body =
    wrapper && boundary ? text.slice(boundary.index + wrapper[0].length) : text;
  let metadata = wrapper ? wrapper[0] : "";
  const frontmatter =
    /^---\r?\n(?:(?:layout|title|nav_order|parent|grand_parent):[^\n]*\r?\n)+---\r?\n/.exec(
      body,
    );
  if (frontmatter) {
    metadata += frontmatter[0];
    body = body.slice(frontmatter[0].length);
  }
  return {
    title:
      wrapper && boundary
        ? boundary[1]
        : "title" in source
          ? source.title
          : source.filename,
    body,
    metadata,
    context: wrapper && boundary ? text.slice(0, boundary.index).trim() : "",
    code: /\.(cfg|ini|py|scl|st|xml|json|csv|log|ya?ml|[ch]|cpp|ts|js)$/i.test(
      wrapper && boundary ? boundary[1] : source.filename,
    ),
  };
}

export function sourceLocation(source: LocalSource) {
  if (source.line_start)
    return `${t("Zeilen")} ${source.line_start}–${source.line_end || source.line_start}`;
  if ("kind" in source && source.kind === "image")
    return t("Eingereichtes Bild");
  if (/\.pdf$/i.test(source.filename) && "page" in source)
    return source.pages?.length
      ? `${t("Seiten")} ${source.pages.join(", ")}`
      : `${t("Seite")} ${source.page}`;
  return t("Textauszug");
}

export function SourceCard({
  source,
  number,
  onOpen,
}: {
  source: LocalSource;
  number: number;
  onOpen: (id: string) => void;
}) {
  useLanguage();
  return (
    <button className="source-card" onClick={() => onOpen(source.citation_id)}>
      <span className="source-card-icon">
        <FileText size={19} />
      </span>
      <span className="source-card-copy">
        <small>
          {t("Quelle")} {number} · {sourceLocation(source)}
        </small>
        <strong>{passage(source).title}</strong>
      </span>
      <ArrowUpRight size={17} aria-hidden="true" />
    </button>
  );
}

function inline(text: string): ReactNode[] {
  // Deliberately no remote images, links, HTML or embedded media.
  return text
    .split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
    .map((part, i) =>
      part.startsWith("**") ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : part.startsWith("`") ? (
        <code key={i}>{part.slice(1, -1)}</code>
      ) : (
        <Fragment key={i}>{part}</Fragment>
      ),
    );
}

function ReadingText({ text }: { text: string }) {
  const lines = text.split(/\r?\n/),
    nodes: ReactNode[] = [];
  for (let i = 0; i < lines.length; ) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    const fence = /^\s*(`{3,}|~{3,})/.exec(line);
    if (fence) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence[1]))
        code.push(lines[i++]);
      if (i < lines.length) i++;
      nodes.push(
        <pre key={i}>
          <code>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }
    if (/^\s*(?:<|!\[)/.test(line)) {
      const markup: string[] = [lines[i++]];
      while (i < lines.length && lines[i].trim()) markup.push(lines[i++]);
      nodes.push(
        <details className="source-markup" key={i}>
          <summary>{t("Medienverweis / Markup (nicht geladen)")}</summary>
          <pre>{markup.join("\n")}</pre>
        </details>,
      );
      continue;
    }
    const heading = /^#{1,6}\s+(.+)$/.exec(line);
    if (heading) {
      nodes.push(<h3 key={i}>{inline(heading[1])}</h3>);
      i++;
      continue;
    }
    const list = /^(?:[-*+] |\d+[.)] )/.exec(line);
    if (list) {
      const items: ReactNode[] = [],
        ordered = /^\d/.test(line);
      while (
        i < lines.length &&
        (ordered ? /^\d+[.)] / : /^[-*+] /).test(lines[i])
      ) {
        items.push(
          <li key={i}>
            {inline(lines[i++].replace(/^(?:[-*+] |\d+[.)] )/, ""))}
          </li>,
        );
      }
      nodes.push(ordered ? <ol key={i}>{items}</ol> : <ul key={i}>{items}</ul>);
      continue;
    }
    const paragraph = [lines[i++]];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(?:#{1,6}\s|[-*+] |\d+[.)] |\s*[<`~]|!\[)/.test(lines[i])
    )
      paragraph.push(lines[i++]);
    nodes.push(<p key={i}>{inline(paragraph.join("\n"))}</p>);
  }
  return <>{nodes}</>;
}

export default function SourceReader({
  source,
  number,
  runId,
  onClose,
}: {
  source: LocalSource;
  number: number;
  runId: string;
  onClose: () => void;
}) {
  useLanguage();
  const dialog = useRef<HTMLDialogElement>(null),
    id = useId();
  const [original, setOriginal] = useState(false);
  const content = passage(source),
    library = "title" in source;
  const image = !library && source.kind === "image";
  const download = library
    ? `/api/investigations/${encodeURIComponent(runId)}/library/documents/${encodeURIComponent(source.id)}/file`
    : `/api/chat/attachments/${encodeURIComponent(source.id)}/file`;
  useEffect(() => {
    const previous = document.activeElement,
      overflow = document.body.style.overflow;
    const el = dialog.current;
    el?.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      el?.close();
      document.body.style.overflow = overflow;
      if (previous instanceof HTMLElement && previous.isConnected)
        previous.focus({ preventScroll: true });
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="source-reader"
      aria-labelledby={id}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <header className="source-reader-head">
        <div>
          <span className="source-reader-eyebrow">
            <FileText size={15} />
            {t("Quelle")} {number} · {sourceLocation(source)}
          </span>
          <h2 id={id}>{content.title}</h2>
          <p>{source.filename}</p>
        </div>
        <button
          className="source-reader-close"
          aria-label={t("Quelle schließen")}
          onClick={onClose}
        >
          <X size={21} />
        </button>
      </header>
      <div className="source-reader-toolbar">
        <div className="source-reader-modes" aria-label={t("Quellenansicht")}>
          <button aria-pressed={!original} onClick={() => setOriginal(false)}>
            {t("Leseansicht")}
          </button>
          <button aria-pressed={original} onClick={() => setOriginal(true)}>
            {t("Originalauszug")}
          </button>
        </div>
        <a href={download} download>
          <Download size={15} />
          <span>{t("Originaldatei")}</span>
        </a>
      </div>
      <div className="source-reader-scroll">
        {image && (
          <figure className="source-reader-image">
            <img
              alt={source.filename}
              src={`/api/chat/attachments/${encodeURIComponent(source.id)}/preview`}
            />
            <figcaption>
              {t(
                "Vom Modell erkannter Text. Prüfe das Originalbild, wenn einzelne Zeichen entscheidend sind.",
              )}
            </figcaption>
          </figure>
        )}
        <div className="source-reader-content">
          <p className="source-reader-label">
            {image ? t("Erkannter Bildtext") : t("Zitierter Dokumentauszug")}
          </p>
          {original ? (
            <pre className="source-reader-raw">{source.text}</pre>
          ) : (
            <>
              {content.code || !library ? (
                <pre className="source-reader-raw">{content.body}</pre>
              ) : (
                <ReadingText text={content.body} />
              )}
              {content.context && (
                <details className="source-context">
                  <summary>{t("Angrenzender Kontext")}</summary>
                  <pre>{content.context}</pre>
                </details>
              )}
            </>
          )}
          <details className="source-reader-provenance">
            <summary>{t("Dokumentdetails und Herkunft")}</summary>
            <dl>
              <div>
                <dt>{t("Dateiname")}</dt>
                <dd>{source.filename}</dd>
              </div>
              <div>
                <dt>{t("Quellenkennung")}</dt>
                <dd>
                  <code>{source.citation_id}</code>
                </dd>
              </div>
              {library ? (
                <>
                  <div>
                    <dt>{t("Produktfamilie")}</dt>
                    <dd>{source.family}</dd>
                  </div>
                  <div>
                    <dt>{t("Version / Handbuchausgabe")}</dt>
                    <dd>{source.version}</dd>
                  </div>
                  <div>
                    <dt>{t("Lizenz und Herkunft")}</dt>
                    <dd>{source.license_note}</dd>
                  </div>
                </>
              ) : (
                <div>
                  <dt>SHA-256</dt>
                  <dd>
                    <code>{source.sha256}</code>
                  </dd>
                </div>
              )}
            </dl>
            {content.metadata && <pre>{content.metadata}</pre>}
          </details>
        </div>
      </div>
      <footer>
        {t(
          "Auszug aus dem gespeicherten Quellenstand. Die Originalsprache bleibt erhalten.",
        )}
      </footer>
    </dialog>
  );
}
