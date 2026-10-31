import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";

const session = vi.hoisted(() => ({
  user: { id: "member", role: "member", username: "member" },
}));
vi.mock("./AuthGate", () => ({ useCurrentUser: () => session.user }));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});
beforeEach(() => {
  session.user = { id: "member", role: "member", username: "member" };
});
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });

it("a member asks a German PLC question in normal chat; the backend owns public routing", async () => {
  history.replaceState(null, "", "/?view=advanced&page=machines");
  const bodies: FormData[] = [];
  const paths: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      paths.push(path);
      if (path === "/api/chat/questions") {
        bodies.push(init!.body as FormData);
        return json({ id: "r", status: "queued", chat_context: { id: "c" } });
      }
      if (path === "/api/chat/conversations/c")
        return json({ id: "c", title: "Problem", turns: [], attachments: [] });
      return json({ conversations: [] });
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  expect(screen.queryByText("Erweitert")).toBeNull();
  expect(screen.queryByText("Maschinenwissen")).toBeNull();
  expect(screen.queryByText("Notizbücher")).toBeNull();
  await user.type(
    screen.getByRole("textbox", { name: "Beschreibe dein Problem" }),
    "Meine Maschine XY mit S7-1500 zeigt Fehlercode 16#80A1",
  );
  const file = new File(["ERROR E17 private log"], "error.log", {
    type: "text/plain",
  });
  await user.upload(
    screen.getByLabelText("Bilder oder Fehlerprotokolle anhängen"),
    file,
  );
  await user.click(screen.getByRole("button", { name: "Problem senden" }));
  expect(bodies[0].get("question")).toBe(
    "Meine Maschine XY mit S7-1500 zeigt Fehlercode 16#80A1",
  );
  expect((bodies[0].get("files") as File).name).toBe("error.log");
  expect(bodies[0].has("machine_id")).toBe(false);
  expect(bodies[0].has("document_ids")).toBe(false);
  expect(paths.some((p) => p.includes("siemens"))).toBe(false);
  expect(
    screen.getByText(/Mit „nur lokal“ bleibt die Frage lokal/),
  ).toBeTruthy();
});

it("shows an unavailable automatic Siemens lookup in German even without source links", async () => {
  history.replaceState(null, "", "/?chat=c");
  const run = {
    id: "r",
    question: "S7-1500 Fehler 16#80A1",
    status: "completed",
    result: { answer: "Die öffentliche Suche ist derzeit nicht verfügbar." },
    chat_context: { id: "c" },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path.endsWith("/export"))
        return json({
          answer: run.result.answer,
          library_citations: [],
          problem_citations: [],
          external_references: [],
          integrations: {
            siemens: {
              enabled: true,
              query_origin: "canonical-human-diagnostic",
              status: "finished",
              remote_search_status: "unavailable",
              connection_verified: false,
              outbound_query: "SIMATIC S7-1500: Diagnose zu 16#80A1.",
            },
          },
        });
      if (path === "/api/chat/conversations/c")
        return json({
          id: "c",
          title: "Diagnose",
          turns: [run],
          attachments: [],
        });
      return json({ conversations: [] });
    }),
  );
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "Siemens-Dokumentation" }),
  ).toBeTruthy();
  expect(
    screen.getByText(/Siemens-Livesuche war nicht verfügbar/),
  ).toBeTruthy();
  expect(screen.getByText(/Automatische Suche: nur die erkannte/)).toBeTruthy();
  expect(
    screen.getByText("SIMATIC S7-1500: Diagnose zu 16#80A1."),
  ).toBeTruthy();
});

it("preserves the problem and attachments after failure with an idempotent retry", async () => {
  const bodies: FormData[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path === "/api/chat/questions") {
        bodies.push(init!.body as FormData);
        return json({ detail: "Queue is busy" }, 409);
      }
      return json({ conversations: [] });
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  const input = screen.getByRole("textbox", {
    name: "Beschreibe dein Problem",
  });
  await user.type(input, "The drive stops");
  await user.upload(
    screen.getByLabelText("Bilder oder Fehlerprotokolle anhängen"),
    new File(["E17"], "error.txt", { type: "text/plain" }),
  );
  await user.click(screen.getByRole("button", { name: "Problem senden" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect((input as HTMLTextAreaElement).value).toBe("The drive stops");
  expect(screen.getByText("error.txt")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Problem senden" }));
  expect(bodies[1].get("request_id")).toBe(bodies[0].get("request_id"));
});

it("an administrator uploads machine data without naming or selecting a machine", async () => {
  session.user = { id: "admin", role: "admin", username: "admin" };
  history.replaceState(null, "", "/?page=machines");
  const bodies: FormData[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        bodies.push(init.body as FormData);
        return json({ id: "job", status: "queued" });
      }
      return json({ machines: [], jobs: [] });
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  expect(screen.queryByRole("textbox", { name: "Maschinenname" })).toBeNull();
  await user.upload(
    screen.getByLabelText("Maschinen-Quelldateien"),
    new File(["Machine ID: XR7"], "manual.md", { type: "text/markdown" }),
  );
  await user.click(
    screen.getByRole("checkbox", {
      name: /berechtigt, diese Dateien/,
    }),
  );
  const fileInput = screen.getByLabelText(
    "Maschinen-Quelldateien",
  ) as HTMLInputElement;
  expect(fileInput.files?.length).toBe(1);
  expect(fileInput.form?.checkValidity()).toBe(true);
  await user.click(
    screen.getByRole("button", { name: "Hochladen und automatisch zuordnen" }),
  );
  expect(await screen.findByRole("status")).toBeTruthy();
  expect((bodies[0].get("file") as File).name).toBe("manual.md");
  expect(bodies[0].has("machine_id")).toBe(false);
});

it("machine ambiguity is a conversational question, with no source or notebook setup", async () => {
  history.replaceState(null, "", "/?chat=c");
  const run = {
    id: "r",
    question: "The line stops",
    status: "completed",
    result: { answer: "Welche Maschine ist betroffen — XR7 oder AB9?" },
    chat_context: { id: "c" },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path.endsWith("/export"))
        return json({
          answer: run.result.answer,
          answer_contract: { outcome: "clarification_required", issues: [] },
          catalog_routing: { status: "needs_clarification" },
          library_citations: [],
          problem_citations: [],
        });
      if (path === "/api/chat/conversations/c")
        return json({
          id: "c",
          title: "Problem",
          turns: [run],
          attachments: [],
        });
      return json({ conversations: [] });
    }),
  );
  render(<App />);
  expect(
    await screen.findByText("Welche Maschine ist betroffen — XR7 oder AB9?"),
  ).toBeTruthy();
  expect(
    screen.getByRole("textbox", { name: "Gespräch fortsetzen" }),
  ).toBeTruthy();
  expect(
    screen.queryByText("Auswahl für nächste Antwort speichern"),
  ).toBeNull();
});

it("an admin explicitly records the public license and provenance before publication", async () => {
  session.user = { id: "admin", role: "admin", username: "admin" };
  history.replaceState(null, "", "/?page=machines");
  const bodies: FormData[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        bodies.push(init.body as FormData);
        return json({ id: "job", status: "queued" });
      }
      return json({ machines: [], jobs: [] });
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await user.upload(
    screen.getByLabelText("Maschinen-Quelldateien"),
    new File(["# Public Voron documentation"], "voron.md", {
      type: "text/markdown",
    }),
  );
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Inhaltstyp" }),
    "licensed-public",
  );
  await user.click(
    screen.getByRole("checkbox", { name: /berechtigt, diese Dateien/ }),
  );
  await user.click(
    screen.getByRole("button", { name: "Hochladen und automatisch zuordnen" }),
  );
  expect(bodies).toHaveLength(0);
  await user.type(
    screen.getByRole("textbox", { name: "Lizenz und Herkunft" }),
    "GPL-3.0; Voron Design; pinned official sources and full license included.",
  );
  await user.click(
    screen.getByRole("button", { name: "Hochladen und automatisch zuordnen" }),
  );
  expect(await screen.findByRole("status")).toBeTruthy();
  expect(bodies[0].get("data_policy")).toBe("licensed-public");
  expect(bodies[0].get("license_note")).toContain("GPL-3.0; Voron Design");
});
