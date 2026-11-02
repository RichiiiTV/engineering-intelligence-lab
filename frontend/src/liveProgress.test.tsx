import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import LiveProgress, { parseProgress } from "./LiveProgress";
import ChatApp from "./ChatApp";
import { setLanguage } from "./i18n";

vi.mock("./AuthGate", () => ({ useCurrentUser: () => ({ role: "member" }) }));

function openStream(signal?: AbortSignal) {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(value) {
      controller = value;
    },
  });
  signal?.addEventListener("abort", () => {
    try {
      controller.error(new DOMException("Aborted", "AbortError"));
    } catch {
      /* Already closed. */
    }
  });
  return { controller, response: new Response(body) };
}
const event = (id: number, stage: string, status?: string) =>
  `id: ${id}\nevent: progress\ndata: ${JSON.stringify({ id, stage, ...(status ? { status } : {}) })}\n\n`;
async function settle() {
  await act(async () => {
    for (let i = 0; i < 18; i++) await Promise.resolve();
  });
}
async function send(
  controller: ReadableStreamDefaultController<Uint8Array>,
  value: string,
) {
  await act(async () => {
    controller.enqueue(new TextEncoder().encode(value));
  });
  await settle();
}
function visibility(value: "hidden" | "visible") {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value,
  });
  fireEvent(document, new Event("visibilitychange"));
}
beforeEach(() => {
  vi.useFakeTimers();
  localStorage.removeItem("eil-live-progress-v1");
  setLanguage("de");
  visibility("visible");
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  localStorage.removeItem("eil-live-progress-v1");
  delete (document as unknown as { visibilityState?: string }).visibilityState;
  history.replaceState(null, "", "/");
});

it("accepts only bounded fixed progress fields and rejects arbitrary content", () => {
  expect(parseProgress(event(4, "generating"))).toEqual({
    id: 4,
    stage: "generating",
  });
  for (const value of [
    { id: 1, stage: "prompt secret" },
    { id: 1, stage: "generating", answer: "private answer" },
    { id: -1, stage: "generating" },
    { id: Number.MAX_SAFE_INTEGER + 1, stage: "generating" },
    { id: 1, stage: "completed", status: "failed" },
    { id: 1, stage: "stopped", status: "running" },
  ])
    expect(
      parseProgress("event: progress\ndata: " + JSON.stringify(value)),
    ).toBeNull();
  expect(
    parseProgress("event: progress\ndata: " + "x".repeat(2000)),
  ).toBeNull();
  expect(
    parseProgress('event: message\ndata: {"id":1,"stage":"generating"}'),
  ).toBeNull();
});

it("streams labels only, resumes at its cursor, and refreshes the final answer once", async () => {
  const streams: ReturnType<typeof openStream>[] = [];
  const paths: string[] = [];
  const onTerminal = vi.fn(async () => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init: RequestInit) => {
      paths.push(path);
      const next = openStream(init.signal as AbortSignal);
      streams.push(next);
      return next.response;
    }),
  );
  render(<LiveProgress runId="a" status="running" onTerminal={onTerminal} />);
  await settle();
  await send(streams[0].controller, event(7, "generating"));
  expect(screen.getByRole("status").textContent).toContain(
    "Antwort wird erarbeitet",
  );
  await act(async () => {
    streams[0].controller.close();
  });
  await settle();
  expect(screen.getByText(/Live-Fortschritt unterbrochen/)).toBeTruthy();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  expect(paths).toEqual([
    "/api/investigations/a/progress?after=0",
    "/api/investigations/a/progress?after=7",
  ]);
  await send(
    streams[1].controller,
    event(8, "completed", "completed") + event(8, "completed", "completed"),
  );
  expect(onTerminal).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("status").textContent).toBe("Antwort bereit");
});

it("aborts hidden/unmounted streams and preserves the cursor on visibility return", async () => {
  const signals: AbortSignal[] = [];
  const streams: ReturnType<typeof openStream>[] = [];
  const paths: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init: RequestInit) => {
      paths.push(path);
      signals.push(init.signal as AbortSignal);
      const next = openStream(init.signal as AbortSignal);
      streams.push(next);
      return next.response;
    }),
  );
  const view = render(
    <LiveProgress runId="a" status="running" onTerminal={async () => {}} />,
  );
  await settle();
  await send(streams[0].controller, event(5, "retrieving"));
  visibility("hidden");
  await settle();
  expect(signals[0].aborted).toBe(true);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(paths).toHaveLength(1);
  visibility("visible");
  await settle();
  expect(paths[1]).toContain("after=5");
  view.unmount();
  expect(signals[1].aborted).toBe(true);
});

it("discards late old-run responses and aborts when the current run is cancelled", async () => {
  let resolve!: (value: Response) => void;
  const old = new Promise<Response>((yes) => {
    resolve = yes;
  });
  const signals: AbortSignal[] = [];
  const current = openStream();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init: RequestInit) => {
      signals.push(init.signal as AbortSignal);
      return path.includes("/a/") ? old : current.response;
    }),
  );
  const view = render(
    <LiveProgress runId="a" status="running" onTerminal={async () => {}} />,
  );
  await settle();
  view.rerender(
    <LiveProgress runId="b" status="running" onTerminal={async () => {}} />,
  );
  await settle();
  await act(async () => {
    resolve(new Response(event(99, "completed", "completed")));
  });
  await send(current.controller, event(2, "retrieving"));
  expect(screen.getByRole("status").textContent).toBe(
    "Passende Quellen werden gelesen…",
  );
  expect(signals[0].aborted).toBe(true);
  view.rerender(
    <LiveProgress runId="b" status="cancelled" onTerminal={async () => {}} />,
  );
  expect(signals[1].aborted).toBe(true);
  expect(screen.getByRole("status").textContent).toBe(
    "Untersuchung angehalten",
  );
});

it("keeps a bounded retry policy and shows no server error/answer contents", async () => {
  const fetcher = vi.fn(
    async () => new Response("Generated private error", { status: 401 }),
  );
  vi.stubGlobal("fetch", fetcher);
  render(
    <LiveProgress runId="a" status="running" onTerminal={async () => {}} />,
  );
  await settle();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(30000);
  });
  expect(fetcher).toHaveBeenCalledTimes(4);
  expect(screen.getByText(/Der Status wird weiter aktualisiert/)).toBeTruthy();
  expect(document.body.textContent).not.toContain("private error");
});

it("switches progress UI language without reconnecting or changing an answer/run", async () => {
  const next = openStream();
  const fetcher = vi.fn(async () => next.response);
  vi.stubGlobal("fetch", fetcher);
  render(
    <LiveProgress runId="a" status="running" onTerminal={async () => {}} />,
  );
  await settle();
  await send(next.controller, event(1, "generating"));
  act(() => setLanguage("en"));
  expect(screen.getByRole("status").textContent).toBe("Working on the answer…");
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("is opt-in, remembers only browser preference, and preserves a chat draft", async () => {
  const paths: string[] = [];
  const next = openStream();
  history.replaceState(null, "", "/?chat=c");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      paths.push(path);
      if (path.includes("/progress")) return next.response;
      if (path.endsWith("/c"))
        return new Response(
          JSON.stringify({
            id: "c",
            title: "Generated chat",
            turns: [
              { id: "a", question: "Generated question", status: "running" },
            ],
            attachments: [],
          }),
        );
      return new Response(JSON.stringify({ conversations: [] }));
    }),
  );
  render(<ChatApp />);
  await settle();
  expect(paths.some((p) => p.includes("/progress"))).toBe(false);
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "Generated draft" },
  });
  fireEvent.click(
    screen.getByRole("checkbox", { name: /Fortschritt live anzeigen/ }),
  );
  await settle();
  expect(paths.filter((p) => p.includes("/progress"))).toHaveLength(1);
  expect(localStorage.getItem("eil-live-progress-v1")).toBe("true");
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(
    "Generated draft",
  );
  expect(paths.some((p) => p.includes("/questions"))).toBe(false);
});
