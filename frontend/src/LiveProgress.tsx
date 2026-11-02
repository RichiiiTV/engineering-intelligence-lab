import { useEffect, useRef, useState } from "react";
import { t, useLanguage } from "./i18n";
import { stopped } from "./useInvestigation";

const stages = new Set([
  "queued",
  "preparing",
  "retrieving",
  "generating",
  "checking",
  "stopping",
  "completed",
  "stopped",
]);
type Progress = { id: number; stage: string; status?: string };

export function parseProgress(block: string): Progress | null {
  if (block.length > 1024) return null;
  if (!block.split("\n").includes("event: progress")) return null;
  const data = block.split("\n").find((line) => line.startsWith("data: "));
  if (!data) return null;
  try {
    const value = JSON.parse(data.slice(6));
    if (
      !value ||
      !Number.isSafeInteger(value.id) ||
      value.id < 0 ||
      !stages.has(value.stage) ||
      Object.keys(value).some(
        (key) => !["id", "stage", "status"].includes(key),
      ) ||
      (value.status !== undefined && !stopped.has(value.status)) ||
      ["completed", "stopped"].includes(value.stage) !==
        (value.status !== undefined) ||
      (value.stage === "completed" && value.status !== "completed") ||
      (value.stage === "stopped" && value.status === "completed")
    )
      return null;
    return value as Progress;
  } catch {
    return null;
  }
}

function stageLabel(stage: string): string {
  const copy: Record<string, string> = {
    queued: "Wartet auf die Untersuchung…",
    preparing: "Untersuchung wird vorbereitet…",
    retrieving: "Passende Quellen werden gelesen…",
    generating: "Antwort wird erarbeitet…",
    checking: "Antwort und Quellen werden vorbereitet…",
    stopping: "Untersuchung wird angehalten…",
    completed: "Antwort bereit",
    stopped: "Untersuchung angehalten",
  };
  return t(copy[stage] || copy.preparing);
}

export default function LiveProgress({
  runId,
  status,
  onTerminal,
}: {
  runId: string;
  status: string;
  onTerminal: () => Promise<void>;
}) {
  useLanguage();
  const [progress, setProgress] = useState<{
    runId: string;
    stage: string;
  } | null>(null);
  const [fallback, setFallback] = useState(false);
  const terminalCallback = useRef(onTerminal);
  terminalCallback.current = onTerminal;
  const terminal = stopped.has(status);
  useEffect(() => {
    if (terminal) return;
    let disposed = false,
      cursor = 0,
      terminalSeen = false,
      failures = 0;
    let active: AbortController | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    setProgress(null);
    setFallback(false);
    async function connect() {
      if (disposed || terminalSeen || document.visibilityState === "hidden")
        return;
      active?.abort();
      const controller = new AbortController();
      active = controller;
      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
      try {
        const response = await fetch(
          `/api/investigations/${runId}/progress?after=${cursor}`,
          {
            signal: controller.signal,
            headers: { Accept: "text/event-stream" },
          },
        );
        if (!response.ok || !response.body)
          throw new Error("Progress unavailable");
        if (disposed || controller.signal.aborted) {
          await response.body.cancel();
          return;
        }
        reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!disposed && !controller.signal.aborted) {
          const { done, value } = await reader.read();
          if (disposed || controller.signal.aborted) return;
          if (done) break;
          buffer = (
            buffer + decoder.decode(value, { stream: true })
          ).replaceAll("\r\n", "\n");
          if (buffer.length > 65536) throw new Error("Progress limit exceeded");
          let boundary: number;
          while ((boundary = buffer.indexOf("\n\n")) >= 0) {
            const event = parseProgress(buffer.slice(0, boundary));
            buffer = buffer.slice(boundary + 2);
            if (!event || event.id < cursor) continue;
            cursor = event.id;
            failures = 0;
            setFallback(false);
            setProgress({ runId, stage: event.stage });
            if (event.status) {
              terminalSeen = true;
              void terminalCallback.current().catch(() => {});
              return;
            }
          }
        }
        if (!terminalSeen) throw new Error("Progress disconnected");
      } catch {
        if (disposed || controller.signal.aborted) return;
        setFallback(true);
        if (++failures <= 3)
          retry = setTimeout(() => void connect(), failures * 1000);
      } finally {
        if (reader) {
          try {
            await reader.cancel();
          } catch {
            /* Already aborted. */
          }
        }
      }
    }
    const visibility = () => {
      clearTimeout(retry);
      if (document.visibilityState === "hidden") active?.abort();
      else {
        failures = 0;
        void connect();
      }
    };
    document.addEventListener("visibilitychange", visibility);
    void connect();
    return () => {
      disposed = true;
      active?.abort();
      clearTimeout(retry);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [runId, terminal]);
  return (
    <span
      className="chat-live-progress"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {terminal
        ? stageLabel(status === "completed" ? "completed" : "stopped")
        : progress?.runId === runId
          ? stageLabel(progress.stage)
          : stageLabel(status === "queued" ? "queued" : "preparing")}
      {fallback && (
        <small>
          {t(
            "Live-Fortschritt unterbrochen. Der Status wird weiter aktualisiert.",
          )}
        </small>
      )}
    </span>
  );
}
