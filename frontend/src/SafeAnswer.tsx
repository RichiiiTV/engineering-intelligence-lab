import { useLanguage, t } from "./i18n";
import { Fragment, type ReactNode } from "react";
import { siemensUrl } from "./siemens";

export default function SafeAnswer({
  text,
  references = [],
  prefix = "",
  onOpenSource,
}: {
  text: string;
  references?: { citation_id: string; title?: string; url?: string }[];
  prefix?: string;
  onOpenSource?: (citationId: string) => void;
}) {
  useLanguage();
  function inline(value: string): ReactNode[] {
    return value
      .split(
        /(\[(?:kb|log|image|pdf|csv|siemens):[^\]]+\]|\*\*[^*]+\*\*|`[^`]+`)/g,
      )
      .map((part, i) => {
        const normalized =
          part.startsWith("`") && part.endsWith("`") ? part.slice(1, -1) : part;
        const ref = references.find(
          (r) => "[" + r.citation_id + "]" === normalized,
        );
        if (
          ref?.citation_id.startsWith("siemens:") &&
          ref.url &&
          siemensUrl(ref.url)
        )
          return (
            <a key={i} href={ref.url} target="_blank" rel="noopener noreferrer">
              {t("[Siemens-Quelle")}{" "}
              {references
                .filter((r) => r.citation_id.startsWith("siemens:"))
                .indexOf(ref) + 1}
              ]
            </a>
          );
        if (ref && /^(kb|log|image):/.test(ref.citation_id))
          return (
            <button
              className="source-inline"
              key={i}
              title={ref.title || t("Quellabschnitt öffnen")}
              onClick={() => {
                if (onOpenSource) {
                  onOpenSource(ref.citation_id);
                  return;
                }
                const target = document.getElementById(
                  prefix + "source-" + ref.citation_id,
                );
                if (target instanceof HTMLDetailsElement) {
                  target.open = true;
                  let parent = target.parentElement;
                  while (parent) {
                    if (parent instanceof HTMLDetailsElement)
                      parent.open = true;
                    parent = parent.parentElement;
                  }
                  target.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                  });
                  target.focus();
                }
              }}
            >
              {t("[Quelle")} {references.indexOf(ref) + 1}]
            </button>
          );
        if (part.startsWith("**") && part.endsWith("**"))
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (part.startsWith("`") && part.endsWith("`"))
          return <code key={i}>{part.slice(1, -1)}</code>;
        return <Fragment key={i}>{part}</Fragment>;
      });
  }
  function prose(value: string): ReactNode[] {
    const lines = value.split(/\r?\n/),
      nodes: ReactNode[] = [];
    const listItem = /^\s*(?:[-*+] |\d+[.)] )/;
    for (let i = 0; i < lines.length; ) {
      const key = i,
        line = lines[i];
      if (!line.trim()) {
        i++;
        continue;
      }
      const heading = /^#{1,4}\s+(.+)$/.exec(line);
      if (heading) {
        nodes.push(<h3 key={key}>{inline(heading[1])}</h3>);
        i++;
        continue;
      }
      if (listItem.test(line)) {
        const ordered = /^\s*\d/.test(line),
          items: ReactNode[] = [],
          start = ordered ? Number.parseInt(line.trim(), 10) : 1;
        while (
          i < lines.length &&
          (ordered ? /^\s*\d+[.)] / : /^\s*[-*+] /).test(lines[i])
        ) {
          items.push(
            <li key={i}>{inline(lines[i++].replace(listItem, ""))}</li>,
          );
        }
        nodes.push(
          ordered ? (
            <ol key={key} start={start}>
              {items}
            </ol>
          ) : (
            <ul key={key}>{items}</ul>
          ),
        );
        continue;
      }
      if (/^> ?/.test(line)) {
        const quote: string[] = [];
        while (i < lines.length && /^> ?/.test(lines[i]))
          quote.push(lines[i++].replace(/^> ?/, ""));
        nodes.push(
          <blockquote key={key}>{inline(quote.join("\n"))}</blockquote>,
        );
        continue;
      }
      const paragraph = [lines[i++]];
      while (
        i < lines.length &&
        lines[i].trim() &&
        !/^#{1,4}\s|^> ?/.test(lines[i]) &&
        !listItem.test(lines[i])
      )
        paragraph.push(lines[i++]);
      nodes.push(<p key={key}>{inline(paragraph.join("\n"))}</p>);
    }
    return nodes;
  }
  const blocks = text.split(/(```[\s\S]*?```)/g);
  return (
    <div className="safe-answer">
      {blocks.map((block, b) =>
        block.startsWith("```") ? (
          <pre key={b}>
            <code>
              {block.replace(/^```[^\n]*\n?/, "").replace(/```$/, "")}
            </code>
          </pre>
        ) : (
          <Fragment key={b}>{prose(block)}</Fragment>
        ),
      )}
    </div>
  );
}
