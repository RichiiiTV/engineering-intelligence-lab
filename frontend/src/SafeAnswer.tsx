import { Fragment, type ReactNode } from "react";

export default function SafeAnswer({
  text,
  references = [],
  prefix = "",
}: {
  text: string;
  references?: { citation_id: string; title?: string }[];
  prefix?: string;
}) {
  function inline(value: string): ReactNode[] {
    return value
      .split(/(\[(?:kb|pdf|csv|siemens):[^\]]+\]|\*\*[^*]+\*\*|`[^`]+`)/g)
      .map((part, i) => {
        const ref = references.find((r) => "[" + r.citation_id + "]" === part);
        if (ref && ref.citation_id.startsWith("kb:"))
          return (
            <button
              className="source-inline"
              key={i}
              title={ref.title || "Open source passage"}
              onClick={() => {
                const target = document.getElementById(
                  prefix + "source-" + ref.citation_id,
                );
                if (target instanceof HTMLDetailsElement) {
                  target.open = true;
                  target.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                  });
                  target.focus();
                }
              }}
            >
              [Source {references.indexOf(ref) + 1}]
            </button>
          );
        if (part.startsWith("**") && part.endsWith("**"))
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (part.startsWith("`") && part.endsWith("`"))
          return <code key={i}>{part.slice(1, -1)}</code>;
        return <Fragment key={i}>{part}</Fragment>;
      });
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
          <Fragment key={b}>
            {block
              .split(/\n\s*\n/)
              .filter(Boolean)
              .map((paragraph, i) => {
                if (
                  /^[-*] /m.test(paragraph) &&
                  paragraph.split("\n").every((l) => /^[-*] /.test(l))
                )
                  return (
                    <ul key={i}>
                      {paragraph.split("\n").map((l, n) => (
                        <li key={n}>{inline(l.slice(2))}</li>
                      ))}
                    </ul>
                  );
                if (/^> /.test(paragraph))
                  return (
                    <blockquote key={i}>
                      {inline(paragraph.replace(/^> /gm, ""))}
                    </blockquote>
                  );
                if (/^#{1,4} /.test(paragraph))
                  return (
                    <h3 key={i}>{inline(paragraph.replace(/^#{1,4} /, ""))}</h3>
                  );
                return <p key={i}>{inline(paragraph)}</p>;
              })}
          </Fragment>
        ),
      )}
    </div>
  );
}
