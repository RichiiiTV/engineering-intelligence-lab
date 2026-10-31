import { tr } from "./i18n";
import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Run, RunEvent } from "./types";

export const stopped = new Set([
  "completed",
  "failed",
  "paused",
  "cancelled",
  "interrupted",
  "timed_out",
  "budget_exceeded",
]);
export function parseEvent(block: string): RunEvent | null {
  const line = block.split("\n").find((x) => x.startsWith("data: "));
  if (!line) return null;
  try {
    return JSON.parse(line.slice(6)) as RunEvent;
  } catch {
    return null;
  }
}
export function mergeEvents(
  previous: RunEvent[],
  incoming: RunEvent,
  runId: string,
): RunEvent[] {
  if (incoming.run_id !== runId || previous.some((x) => x.id === incoming.id))
    return previous;
  return [...previous, incoming].sort((a, b) => a.id - b.id);
}
export function useInvestigation(id: string, revision: number) {
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState("");
  const previousId = useRef("");
  useEffect(() => {
    if (previousId.current !== id) setRun(null);
    previousId.current = id;
    setEvents([]);
    setError("");
    if (!id) return;
    const controller = new AbortController();
    const { signal } = controller;
    let cursor = 0;
    const status = async () => {
      try {
        const next = await api<Run>(`/api/investigations/${id}`, { signal });
        if (!signal.aborted) setRun(next);
        return next;
      } catch (e) {
        if (!signal.aborted) setError(String(e));
        return null;
      }
    };
    const timer = setInterval(() => void status(), 1500);
    void status();
    void (async () => {
      while (!signal.aborted) {
        try {
          const response = await fetch(
            `/api/investigations/${id}/events?after=${cursor}`,
            { signal },
          );
          if (!response.ok || !response.body)
            throw new Error(
              tr`Ereignisstrom nicht verfügbar (${response.status})`,
            );
          const reader = response.body.getReader(),
            decoder = new TextDecoder();
          let buffer = "";
          while (!signal.aborted) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder
              .decode(value, { stream: true })
              .replaceAll("\r\n", "\n");
            let boundary: number;
            while ((boundary = buffer.indexOf("\n\n")) >= 0) {
              const event = parseEvent(buffer.slice(0, boundary));
              buffer = buffer.slice(boundary + 2);
              if (event && event.run_id === id) {
                cursor = Math.max(cursor, event.id);
                setEvents((previous) => mergeEvents(previous, event, id));
              }
            }
          }
          setError("");
          const current = await status();
          if (current && stopped.has(current.status)) break;
        } catch (e) {
          if (!signal.aborted) setError(String(e));
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    })();
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [id, revision]);
  return { run, events, error };
}
