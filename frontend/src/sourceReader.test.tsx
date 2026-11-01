import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatApp from "./ChatApp";
import SourceReader, { sourceLocation, type LocalSource } from "./SourceReader";
import { setLanguage } from "./i18n";

vi.mock("./AuthGate", () => ({ useCurrentUser: () => ({ role: "member" }) }));
beforeEach(() => {
  setLanguage("de");
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
      this.querySelector<HTMLButtonElement>("button")?.focus();
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.removeAttribute("open");
    },
  });
});
afterEach(() => {
  cleanup();
  setLanguage("de");
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});

const source = {
  id: "doc",
  citation_id: "kb:doc:p1:c2",
  title: "Machine manual",
  filename: "machine.md",
  page: 1,
  text:
    "Earlier fragment\n\n## Upstream source: Gantry Squaring\n\nOriginal source: https://github.com/example/manual/blob/commit/gantry.md\n\nCommit: " +
    "a".repeat(40) +
    "\n\nSHA-256 of original bytes: " +
    "b".repeat(64) +
    "\n\n``````text\n---\nlayout: default\ntitle: Gantry Squaring\n---\n# Gantry Squaring\nPoor squaring can cause:\n- First layer issues\n- Belts rubbing\n\n<video src=\"https://example.invalid/video\"></video>\n<script>alert('untrusted')</script>",
  family: "Demo",
  version: "v1",
  license_note: "Generated test fixture",
  data_policy: "synthetic",
  cited_in_answer: true,
};

it("opens the cited frozen passage in normal chat without expanding or scrolling the source list; closing restores focus", async () => {
  history.replaceState(null, "", "/?chat=c");
  const run = {
    id: "run",
    question: "Why are the belts rubbing?",
    status: "completed",
    result: {
      answer: `Check squaring [${source.citation_id}]. Unknown [kb:missing:p1:c0].`,
    },
    chat_context: { id: "c" },
  };
  const fetch = vi.fn(
    async (path: string) =>
      new Response(
        JSON.stringify(
          path.endsWith("/export")
            ? {
                answer: run.result.answer,
                machine_id: "m",
                library_snapshot: [{ id: "doc" }],
                library_citations: [source],
              }
            : path.endsWith("/c")
              ? { id: "c", turns: [run], attachments: [] }
              : { conversations: [] },
        ),
      ),
  );
  vi.stubGlobal("fetch", fetch);
  render(<ChatApp />);
  const user = userEvent.setup(),
    trigger = await screen.findByRole("button", { name: "[Quelle 1]" });
  const requests = fetch.mock.calls.length;
  await user.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "Gantry Squaring" });
  expect(within(dialog).getByText("Belts rubbing")).toBeTruthy();
  expect(
    (document.querySelector(".chat-sources") as HTMLDetailsElement).open,
  ).toBe(false);
  expect(fetch.mock.calls.length).toBe(requests);
  expect(
    within(dialog)
      .getByRole("link", { name: "Originaldatei" })
      .getAttribute("href"),
  ).toBe("/api/investigations/run/library/documents/doc/file");
  expect(screen.queryByRole("button", { name: /missing/ })).toBeNull();
  await user.click(
    within(dialog).getByRole("button", { name: "Quelle schließen" }),
  );
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(trigger);
  expect(document.body.style.overflow).toBe("");
  await user.click(screen.getByText(/^Quellen · 1$/));
  await user.click(
    screen.getByRole("button", {
      name: /Quelle 1 · Textauszug Gantry Squaring/,
    }),
  );
  expect(screen.getByRole("dialog", { name: "Gantry Squaring" })).toBeTruthy();
});

it("keeps an exact original and provenance while formatting lists and preventing remote media or HTML execution", async () => {
  render(
    <SourceReader source={source} number={3} runId="run" onClose={vi.fn()} />,
  );
  const dialog = screen.getByRole("dialog"),
    user = userEvent.setup();
  expect(within(dialog).getAllByRole("listitem").length).toBe(2);
  expect(dialog.querySelector("script,video,iframe,img")).toBeNull();
  expect(within(dialog).getByText("Angrenzender Kontext")).toBeTruthy();
  await user.click(
    within(dialog).getByRole("button", { name: "Originalauszug" }),
  );
  expect(dialog.querySelector(".source-reader-raw")?.textContent).toBe(
    source.text,
  );
  await user.click(within(dialog).getByText("Dokumentdetails und Herkunft"));
  expect(within(dialog).getByText(source.citation_id)).toBeTruthy();
  expect(within(dialog).getByText("Generated test fixture")).toBeTruthy();
  expect(dialog.querySelector("script,video,iframe,img")).toBeNull();
});

it("uses private attachment endpoints and preserves config/log text as code", () => {
  const log: LocalSource = {
    id: "private-id",
    citation_id: "log:private-id:L4-L5",
    filename: "fault.log",
    kind: "log",
    text: "# Log heading\nERROR E17\n  spacing retained",
    line_start: 4,
    line_end: 5,
    sha256: "abc",
  };
  render(
    <SourceReader source={log} number={2} runId="run" onClose={vi.fn()} />,
  );
  expect(screen.getByText("Quelle 2 · Zeilen 4–5")).toBeTruthy();
  expect(document.querySelector(".source-reader-raw")?.textContent).toBe(
    log.text,
  );
  expect(screen.queryByRole("heading", { name: "Log heading" })).toBeNull();
  expect(
    screen.getByRole("link", { name: "Originaldatei" }).getAttribute("href"),
  ).toBe("/api/chat/attachments/private-id/file");
});

it("labels actual PDF pages and text excerpts in English without translating source content", async () => {
  setLanguage("en");
  expect(
    sourceLocation({ ...source, filename: "manual.pdf", pages: [7, 8] }),
  ).toBe("pages 7, 8");
  expect(sourceLocation({ ...source, filename: "manual.pdf", page: 9 })).toBe(
    "Page 9",
  );
  expect(sourceLocation(source)).toBe("Text excerpt");
  render(
    <SourceReader
      source={{ ...source, text: "Originaler deutscher Quellentext." }}
      number={1}
      runId="run"
      onClose={vi.fn()}
    />,
  );
  expect(screen.getByRole("button", { name: "Reading view" })).toBeTruthy();
  expect(screen.getByText("Originaler deutscher Quellentext.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Close source" })).toBeTruthy();
});

it("closes on native Escape cancellation and exposes only the authenticated image preview", () => {
  const close = vi.fn();
  const image: LocalSource = {
    id: "image-id",
    citation_id: "image:image-id",
    filename: "error.png",
    kind: "image",
    text: "E17 (uncertain)",
    sha256: "abc",
  };
  render(
    <SourceReader source={image} number={1} runId="run" onClose={close} />,
  );
  expect(screen.getByRole("img").getAttribute("src")).toBe(
    "/api/chat/attachments/image-id/preview",
  );
  expect(screen.getByText(/Vom Modell erkannter Text/)).toBeTruthy();
  fireEvent(
    screen.getByRole("dialog"),
    new Event("cancel", { cancelable: true }),
  );
  expect(close).toHaveBeenCalledOnce();
});
