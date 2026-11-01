import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ChatApp from "./ChatApp";
import { setLanguage } from "./i18n";

vi.mock("./AuthGate", () => ({ useCurrentUser: () => ({ role: "member" }) }));

const json = (body: unknown) => new Response(JSON.stringify(body));
const run = (status = "queued", id = "c") => ({
  id: "run-" + id,
  question: "Question " + id,
  status,
  result: status === "completed" ? { answer: "Finished " + id } : null,
  chat_context: { id },
});
const detail = (status = "queued", id = "c") => ({
  id,
  title: "Chat " + id,
  turns: [run(status, id)],
  attachments: [],
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i++) await Promise.resolve();
  });
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
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
  setLanguage("de");
  history.replaceState(null, "", "/?chat=c");
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  delete (document as unknown as { visibilityState?: string }).visibilityState;
  history.replaceState(null, "", "/");
});

it("serializes active polling and stops when the run completes", async () => {
  const pending = deferred<Response>();
  let reads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/chat/conversations/c")
        return ++reads === 1 ? json(detail()) : pending.promise;
      if (path.endsWith("/export")) return json({ answer: "Finished c" });
      return json({ conversations: [{ id: "c", title: "Chat c" }] });
    }),
  );
  render(<ChatApp />);
  await settle();
  expect(reads).toBe(1);
  await advance(1500);
  expect(reads).toBe(2);
  await advance(10000);
  expect(reads).toBe(2);
  await act(async () => {
    pending.resolve(json(detail("completed")));
  });
  await settle();
  expect(screen.getByText("Finished c")).toBeTruthy();
  await advance(60000);
  expect(reads).toBe(2);
});

it("does not poll an idle completed chat and refreshes when it becomes visible", async () => {
  let reads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/chat/conversations/c") {
        reads++;
        return json(detail("completed"));
      }
      if (path.endsWith("/export")) return json({ answer: "Finished c" });
      return json({ conversations: [] });
    }),
  );
  render(<ChatApp />);
  await settle();
  await advance(60000);
  expect(reads).toBe(1);
  visibility("hidden");
  await advance(60000);
  expect(reads).toBe(1);
  visibility("visible");
  await settle();
  expect(reads).toBe(2);
  await advance(60000);
  expect(reads).toBe(2);
});

it("pauses active polling while hidden and resumes on return", async () => {
  let reads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/chat/conversations/c") {
        reads++;
        return json(detail());
      }
      return json({ conversations: [] });
    }),
  );
  render(<ChatApp />);
  await settle();
  visibility("hidden");
  await advance(30000);
  expect(reads).toBe(1);
  visibility("visible");
  await settle();
  expect(reads).toBe(2);
  await advance(1500);
  expect(reads).toBe(3);
});

it.each(["resolve", "reject"])(
  "ignores a late %s from the previous conversation",
  async (outcome) => {
    const old = deferred<Response>();
    const signals: AbortSignal[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, init?: RequestInit) => {
        if (path === "/api/chat/conversations/c") {
          signals.push(init!.signal!);
          return old.promise;
        }
        if (path === "/api/chat/conversations/d")
          return json(detail("completed", "d"));
        if (path.endsWith("/export")) return json({ answer: "Finished d" });
        return json({
          conversations: [
            { id: "c", title: "Chat c" },
            { id: "d", title: "Chat d" },
          ],
        });
      }),
    );
    render(<ChatApp />);
    await settle();
    fireEvent.click(screen.getByRole("button", { name: "Deine Chats" }));
    await settle();
    fireEvent.click(screen.getByRole("button", { name: "Chat d" }));
    await settle();
    expect(signals.every((signal) => signal.aborted)).toBe(true);
    expect(screen.getByText("Question d")).toBeTruthy();
    await act(async () => {
      if (outcome === "resolve") old.resolve(json(detail()));
      else old.reject(new Error("Old conversation failure"));
    });
    await settle();
    expect(screen.queryByText("Question c")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("Finished d")).toBeTruthy();
  },
);

it("does not let an older poll overwrite a newer manual refresh", async () => {
  const old = deferred<Response>();
  let reads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/chat/conversations/c") {
        reads++;
        return reads === 2
          ? old.promise
          : json(detail(reads === 1 ? "queued" : "completed"));
      }
      if (path.endsWith("/export")) return json({ answer: "Finished c" });
      return json({ conversations: [] });
    }),
  );
  render(<ChatApp />);
  await settle();
  await advance(1500);
  fireEvent.click(screen.getByRole("button", { name: "Deine Chats" }));
  await settle();
  expect(screen.getByText("Finished c")).toBeTruthy();
  await act(async () => {
    old.resolve(json(detail()));
  });
  await settle();
  expect(screen.queryByText("Wartet auf die Untersuchung…")).toBeNull();
  expect(screen.getByText("Finished c")).toBeTruthy();
});

it("offers an explicit retry after a failed initial load", async () => {
  let reads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/chat/conversations/c") {
        if (++reads === 1) throw new Error("Disconnected");
        return json(detail("completed"));
      }
      if (path.endsWith("/export")) return json({ answer: "Finished c" });
      return json({ conversations: [] });
    }),
  );
  render(<ChatApp />);
  await settle();
  expect(screen.getByRole("alert")).toBeTruthy();
  await advance(30000);
  expect(reads).toBe(1);
  fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
  await settle();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByText("Finished c")).toBeTruthy();
});

it.each([false, true])(
  "preserves a newer draft when a submitted question finishes (switched chat: %s)",
  async (switchChat) => {
    const submitted = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) => {
        if (path === "/api/chat/questions") return submitted.promise;
        if (path === "/api/chat/conversations/c")
          return json(detail("completed"));
        if (path === "/api/chat/conversations/d")
          return json(detail("completed", "d"));
        if (path.endsWith("/export"))
          return json({
            answer: path.includes("run-d") ? "Finished d" : "Finished c",
          });
        return json({
          conversations: [
            { id: "c", title: "Chat c" },
            { id: "d", title: "Chat d" },
          ],
        });
      }),
    );
    render(<ChatApp />);
    await settle();
    const textbox = screen.getByRole("textbox", {
      name: "Gespräch fortsetzen",
    });
    fireEvent.change(textbox, { target: { value: "Submitted question" } });
    fireEvent.submit(textbox.closest("form")!);
    await settle();
    if (switchChat) {
      fireEvent.click(screen.getByRole("button", { name: "Deine Chats" }));
      await settle();
      fireEvent.click(screen.getByRole("button", { name: "Chat d" }));
      await settle();
    }
    fireEvent.change(textbox, { target: { value: "New draft while sending" } });
    await act(async () => {
      submitted.resolve(json(run()));
    });
    await settle();
    expect((textbox as HTMLTextAreaElement).value).toBe(
      "New draft while sending",
    );
    expect(location.search).toBe(switchChat ? "?chat=d" : "?chat=c");
    if (switchChat) expect(screen.getByText("Question d")).toBeTruthy();
  },
);
