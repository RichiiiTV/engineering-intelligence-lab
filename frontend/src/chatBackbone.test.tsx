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

it("a member only describes a problem and attaches a log; no automatic public disclosure", async () => {
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
  expect(screen.queryByText("Advanced")).toBeNull();
  expect(screen.queryByText("Machine knowledge")).toBeNull();
  expect(screen.queryByText("Notebooks")).toBeNull();
  await user.type(
    screen.getByRole("textbox", { name: "Describe your problem" }),
    "Our private S7 line reports E17",
  );
  const file = new File(["ERROR E17 private log"], "error.log", {
    type: "text/plain",
  });
  await user.upload(screen.getByLabelText("Attach images or error logs"), file);
  await user.click(screen.getByRole("button", { name: "Send problem" }));
  expect(bodies[0].get("question")).toBe("Our private S7 line reports E17");
  expect((bodies[0].get("files") as File).name).toBe("error.log");
  expect(bodies[0].has("machine_id")).toBe(false);
  expect(bodies[0].has("document_ids")).toBe(false);
  expect(paths.some((p) => p.includes("siemens"))).toBe(false);
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
  const input = screen.getByRole("textbox", { name: "Describe your problem" });
  await user.type(input, "The drive stops");
  await user.upload(
    screen.getByLabelText("Attach images or error logs"),
    new File(["E17"], "error.txt", { type: "text/plain" }),
  );
  await user.click(screen.getByRole("button", { name: "Send problem" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect((input as HTMLTextAreaElement).value).toBe("The drive stops");
  expect(screen.getByText("error.txt")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Send problem" }));
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
  expect(screen.queryByRole("textbox", { name: "Machine name" })).toBeNull();
  await user.upload(
    screen.getByLabelText("Machine source files"),
    new File(["Machine ID: XR7"], "manual.md", { type: "text/markdown" }),
  );
  await user.click(
    screen.getByRole("checkbox", {
      name: /authorized to make these files available/,
    }),
  );
  const fileInput = screen.getByLabelText(
    "Machine source files",
  ) as HTMLInputElement;
  expect(fileInput.files?.length).toBe(1);
  expect(fileInput.form?.checkValidity()).toBe(true);
  await user.click(
    screen.getByRole("button", { name: "Upload and organize automatically" }),
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
    result: { answer: "Which machine is affected — XR7 or AB9?" },
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
    await screen.findByText("Which machine is affected — XR7 or AB9?"),
  ).toBeTruthy();
  expect(
    screen.getByRole("textbox", { name: "Continue the conversation" }),
  ).toBeTruthy();
  expect(screen.queryByText("Save selection for next answer")).toBeNull();
});
