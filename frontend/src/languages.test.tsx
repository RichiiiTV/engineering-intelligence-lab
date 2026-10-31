import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AuthGate from "./AuthGate";
import App from "./App";
import { getLanguage, setLanguage } from "./i18n";
import { userReport } from "./userReport";
import type { Run, EvidenceReport } from "./types";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
afterEach(() => {
  cleanup();
  setLanguage("de");
  localStorage.clear();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});
function auth(path: string) {
  if (path === "/api/auth/status") return json({ configured: true });
  if (path === "/api/auth/me")
    return json({ user: { id: "u", username: "member", role: "member" } });
  return null;
}

it("switches DE/EN without losing a draft or files and sends the selected language", async () => {
  const bodies: FormData[] = [];
  const headers: Headers[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const session = auth(path);
      if (session) return session;
      if (path === "/api/chat/questions") {
        bodies.push(init!.body as FormData);
        headers.push(new Headers(init!.headers));
        return json({ detail: "Queue is busy" }, 409);
      }
      return json({ conversations: [] });
    }),
  );
  const user = userEvent.setup();
  render(
    <AuthGate>
      <App />
    </AuthGate>,
  );
  const input = await screen.findByRole("textbox", {
    name: "Beschreibe dein Problem",
  });
  await user.type(input, "Mein unveränderter Entwurf XR7");
  await user.upload(
    screen.getByLabelText("Bilder oder Fehlerprotokolle anhängen"),
    new File(["E17"], "error.log", { type: "text/plain" }),
  );
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Sprache / Language" }),
    "en",
  );
  expect(screen.getByRole("textbox", { name: "Describe your problem" })).toBe(
    input,
  );
  expect((input as HTMLTextAreaElement).value).toBe(
    "Mein unveränderter Entwurf XR7",
  );
  expect(screen.getByText("error.log")).toBeTruthy();
  expect(document.documentElement.lang).toBe("en");
  expect(localStorage.getItem("eil-language-v1")).toBe("en");
  await user.click(screen.getByRole("button", { name: "Send problem" }));
  expect(bodies[0].get("language")).toBe("en");
  expect(headers[0].get("X-EIL-Language")).toBe("en");
  expect((bodies[0].get("files") as File).name).toBe("error.log");
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Sprache / Language" }),
    "de",
  );
  expect(screen.getByRole("textbox", { name: "Beschreibe dein Problem" })).toBe(
    input,
  );
  await user.click(screen.getByRole("button", { name: "Problem senden" }));
  expect(bodies[1].get("language")).toBe("de");
  expect(bodies[1].get("request_id")).not.toBe(bodies[0].get("request_id"));
});

it("keeps original answers unchanged while interface labels switch", async () => {
  history.replaceState(null, "", "/?chat=c");
  const run = {
    id: "r",
    question: "XR7",
    status: "completed",
    result: { answer: "Beschreibe dein Problem" },
    chat_context: { id: "c" },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const session = auth(path);
      if (session) return session;
      if (path.endsWith("/export"))
        return json({
          answer: run.result.answer,
          library_citations: [],
          problem_citations: [],
        });
      if (path === "/api/chat/conversations/c")
        return json({ id: "c", turns: [run], attachments: [] });
      return json({ conversations: [] });
    }),
  );
  const user = userEvent.setup();
  render(
    <AuthGate>
      <App />
    </AuthGate>,
  );
  await screen.findByText("Beschreibe dein Problem");
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Sprache / Language" }),
    "en",
  );
  expect(screen.getByText("Beschreibe dein Problem")).toBeTruthy();
  expect(
    screen.getByRole("textbox", { name: "Continue the conversation" }),
  ).toBeTruthy();
});

it("offers the language choice before sign-in and rejects unsupported choices", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      path === "/api/auth/status"
        ? json({ configured: true })
        : json({ detail: "Authentication required" }, 401),
    ),
  );
  const user = userEvent.setup();
  render(
    <AuthGate>
      <App />
    </AuthGate>,
  );
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Sprache / Language" }),
    "en",
  );
  expect(screen.getByLabelText("Username")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
  setLanguage("fr");
  expect(getLanguage()).toBe("en");
  cleanup();
  render(
    <AuthGate>
      <App />
    </AuthGate>,
  );
  expect(
    screen.getByRole("combobox", { name: "Sprache / Language" }),
  ).toHaveProperty("value", "en");
});

it("localizes downloaded report chrome while keeping original answer text escaped", () => {
  setLanguage("en");
  const html = userReport(
    { id: "r", question: "Meine Frage", status: "completed" } as Run,
    {
      answer: "Beschreibe dein Problem <script>unsafe()</script>",
      citations: [],
      uncertainty: { limitations: [] },
    } as unknown as EvidenceReport,
    null,
    "",
  );
  expect(html).toContain('lang="en"');
  expect(html).toContain("Investigation report");
  expect(html).toContain("Limitations");
  expect(html).toContain("Beschreibe dein Problem &lt;script&gt;");
  expect(html).not.toContain("<script>unsafe()");
});
