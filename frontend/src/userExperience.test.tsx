import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createHash, webcrypto } from "node:crypto";
import UserApp from "./UserApp";
import {
  readableAnswer,
  startUserInvestigation,
  validateFiles,
} from "./userFlow";
import { userReport } from "./userReport";
import { tokenContinuation } from "./budgetRecovery";
import type { EvidenceReport, Run, Source } from "./types";

const CASE = "11111111-1111-4111-8111-111111111111",
  RUN = "22222222-2222-4222-8222-222222222222",
  SOURCE = "33333333-3333-4333-8333-333333333333";
const source: Source = {
  id: SOURCE,
  filename: "inspection.csv",
  kind: "csv",
  sha256: createHash("sha256").update("x").digest("hex"),
  size: 1,
  row_count: 2,
  data_policy: "synthetic",
};
const run: Run = {
  id: RUN,
  case_id: CASE,
  question: "Where did rates increase?",
  status: "completed",
  created_at: "2026-10-29T10:00:00Z",
  model: "local",
  model_calls: 2,
  tool_calls: 1,
  tokens: 3000,
  steps: 5,
  elapsed_seconds: 12,
  attempt_started_at: null,
  source_ids: [SOURCE],
  use_mock_mcp: false,
  limits: {
    max_steps: 35,
    max_model_calls: 8,
    max_tool_calls: 16,
    max_total_tokens: 32768,
    max_output_tokens: 2048,
    timeout_seconds: 120,
  },
  error: null,
  result: { answer: "A finding to review.", warning: "Verify sources" },
};
const report: EvidenceReport = {
  answer: "S04 changed most; cause unknown.",
  source_snapshot: [source],
  citations: [],
  citation_checks: {
    unresolved: [],
    not_returned_by_tools: [],
    malformed: [],
    has_answer_citations: false,
  },
  uncertainty: { limitations: ["No causal confidence estimated."] },
};
const comparison = {
  ranking: [
    {
      station_id: "S04",
      baseline_rate: 0.02,
      incident_rate: 0.05,
      delta_percentage_points: 3,
      baseline_inspected: 100,
      incident_inspected: 100,
      supporting_row_count: 2,
      example_citations: [`csv:${SOURCE}:r0`, `csv:${SOURCE}:r1`],
    },
  ],
  query_provenance: { source_id: SOURCE },
  uncertainty: "Descriptive only.",
};
beforeEach(() => {
  history.replaceState(null, "", "/");
  vi.stubGlobal("crypto", webcrypto);
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
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
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});
function mockServer(
  options: {
    uploadFailure?: boolean;
    status?: string;
    foreign?: boolean;
    extraSource?: boolean;
    tokenStop?: boolean;
  } = {},
) {
  const existingAtStart = Boolean(location.search);
  let created = false,
    uploaded = false,
    fail = !!options.uploadFailure;
  let currentStatus = options.status || run.status;
  const fetcher = vi.fn(
    async (input: string | URL | Request, init?: RequestInit) => {
      const path = String(input);
      const json = (body: unknown, status = 200) =>
        new Response(JSON.stringify(body), { status });
      if (path === "/api/cases" && init?.method === "POST") {
        created = true;
        return json(
          {
            id: CASE,
            title: "Where did rates increase?",
            created_at: run.created_at,
          },
          201,
        );
      }
      if (path === "/api/cases")
        return json({
          cases:
            created || existingAtStart
              ? [
                  {
                    id: CASE,
                    title: "Saved investigation",
                    created_at: run.created_at,
                  },
                ]
              : [],
        });
      if (path === `/api/cases/${CASE}`)
        return json({
          id: CASE,
          title: "Saved investigation",
          created_at: run.created_at,
          sources:
            uploaded || existingAtStart
              ? [
                  source,
                  ...(options.extraSource
                    ? [{ ...source, id: "later-source", filename: "later.csv" }]
                    : []),
                ]
              : [],
        });
      if (path === `/api/investigations?case_id=${CASE}&limit=1`)
        return json({ investigations: [run] });
      if (path === `/api/cases/${CASE}/sources` && init?.method === "POST") {
        if (fail) {
          fail = false;
          return json(
            { detail: "CSV columns do not match the inspection schema" },
            422,
          );
        }
        uploaded = true;
        return json(source, 201);
      }
      if (path === "/api/investigations" && init?.method === "POST")
        return json(run, 202);
      if (path === "/api/investigations")
        return json({ investigations: existingAtStart ? [run] : [] });
      if (
        init?.method === "POST" &&
        path.startsWith(`/api/investigations/${RUN}/`)
      ) {
        currentStatus = path.endsWith("/pause")
          ? "paused"
          : path.endsWith("/resume") || path.endsWith("/continue")
            ? "running"
            : "cancelled";
        return json({ ...run, status: currentStatus }, 202);
      }
      if (path.includes("/events?"))
        return new Response(
          new ReadableStream({
            start(controller) {
              controller.close();
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      if (path === `/api/investigations/${RUN}`)
        return json({
          ...run,
          status: currentStatus,
          case_id: options.foreign ? "another-case" : CASE,
          error:
            currentStatus === "budget_exceeded"
              ? {
                  code: "budget_exceeded",
                  message: options.tokenStop
                    ? "tokens budget exhausted; create a new investigation"
                    : "Model output limit reached before completion",
                }
              : null,
        });
      if (path.endsWith("/export")) return json(report);
      if (path.endsWith("/comparison")) return json(comparison);
      if (path.includes("/citations/"))
        return json({
          ...source,
          source_id: SOURCE,
          citation_id: `csv:${SOURCE}:r0`,
          row: {
            row_id: "EXAMPLE-ROW",
            station_id: "S04",
            period: "baseline",
            csv_line: 2,
          },
        });
      throw new Error(`Unexpected request: ${path}`);
    },
  );
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
async function fillForm() {
  await userEvent.type(
    screen.getByLabelText("Deine Frage"),
    "Where did rates increase?",
  );
  await userEvent.upload(
    screen.getByLabelText("CSV- oder PDF-Dateien hinzufügen"),
    new File(["x"], "inspection.csv", { type: "text/csv" }),
  );
  const button = screen.getByRole("button", {
    name: "Untersuchen",
  }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  await userEvent.click(
    screen.getByRole("checkbox", { name: /Ich bestätige, dass diese Dateien/ }),
  );
  expect(button.disabled).toBe(false);
  return button;
}

it("opens an older case through its own history even when the global latest runs omit it", async () => {
  history.replaceState(null, "", "/?page=investigations");
  const fallback = mockServer();
  const fetcher = vi.fn(
    async (input: string | URL | Request, init?: RequestInit) => {
      if (String(input) === "/api/investigations")
        return new Response(JSON.stringify({ investigations: [] }));
      return fallback(input, init);
    },
  );
  vi.stubGlobal("fetch", fetcher);
  render(<UserApp />);
  await userEvent.click(
    await screen.findByRole("button", { name: /Saved investigation/ }),
  );
  await screen.findByText(/S04 changed most/);
  expect(
    fetcher.mock.calls.some(
      ([path]) => path === `/api/investigations?case_id=${CASE}&limit=1`,
    ),
  ).toBe(true);
  expect(new URLSearchParams(location.search).get("run")).toBe(RUN);
});

it("loads another page of cases and deduplicates records", async () => {
  history.replaceState(null, "", "/?page=investigations");
  const fallback = mockServer();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const path = String(input);
      const row = {
        id: CASE,
        title: "First saved case",
        created_at: run.created_at,
      };
      if (path === "/api/cases")
        return new Response(JSON.stringify({ cases: [row], next_offset: 50 }));
      if (path === "/api/cases?offset=50&limit=50")
        return new Response(
          JSON.stringify({
            cases: [row, { ...row, id: "later", title: "Older saved case" }],
            next_offset: null,
          }),
        );
      return fallback(input, init);
    }),
  );
  render(<UserApp />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Weitere Untersuchungen laden" }),
  );
  await screen.findByRole("button", { name: /Older saved case/ });
  expect(
    screen.getAllByRole("button", { name: /First saved case/ }),
  ).toHaveLength(1);
  expect(
    screen.queryByRole("button", { name: "Weitere Untersuchungen laden" }),
  ).toBeNull();
});

it("shows the approved simple entry point without case setup or technical controls", () => {
  mockServer();
  render(<UserApp />);
  expect(
    screen.getByRole("heading", {
      name: "Was möchtest du untersuchen?",
    }),
  ).toBeTruthy();
  expect(screen.queryByLabelText("Fallname")).toBeNull();
  expect(screen.queryByText(/model calls/)).toBeNull();
  expect(
    screen
      .getByRole("link", { name: "Erweiterter Arbeitsbereich" })
      .getAttribute("href"),
  ).toContain("view=advanced");
});
it("creates the case automatically, uploads confirmed files, and opens grounded findings", async () => {
  const fetcher = mockServer();
  render(<UserApp />);
  await userEvent.click(await fillForm());
  await screen.findByRole("heading", {
    name: "Fehlausschuss stieg am stärksten bei S04",
  });
  expect(screen.getAllByText("2.00%")).toHaveLength(2);
  expect(screen.getAllByText("5.00%")).toHaveLength(2);
  const submitted = fetcher.mock.calls.find(
    (c) => c[0] === "/api/investigations" && c[1]?.method === "POST",
  );
  expect(JSON.parse(String(submitted?.[1]?.body))).toMatchObject({
    case_id: CASE,
    use_mock_mcp: false,
    limits: { max_output_tokens: 2048 },
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Vorher: Quellzeile" }),
  );
  const modal = await screen.findByRole("dialog");
  expect(within(modal).getByText("EXAMPLE-ROW")).toBeTruthy();
});
it("keeps an upload failure recoverable and retries without creating a second case", async () => {
  const fetcher = mockServer({ uploadFailure: true });
  render(<UserApp />);
  await userEvent.click(await fillForm());
  await screen.findByText(/CSV-Spalten entsprechen nicht/);
  expect(
    fetcher.mock.calls.some(
      (c) => c[0] === "/api/investigations" && c[1]?.method === "POST",
    ),
  ).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Untersuchen" }));
  await screen.findByRole("heading", {
    name: "Fehlausschuss stieg am stärksten bei S04",
  });
  expect(
    fetcher.mock.calls.filter(
      (c) => c[0] === "/api/cases" && c[1]?.method === "POST",
    ),
  ).toHaveLength(1);
});
it("uses the saved run snapshot even when new files have since been uploaded", async () => {
  history.replaceState(null, "", `/?case=${CASE}&run=${RUN}`);
  const fetcher = mockServer({ extraSource: true });
  render(<UserApp />);
  await screen.findByRole("heading", {
    name: "Fehlausschuss stieg am stärksten bei S04",
  });
  expect(
    fetcher.mock.calls.some((c) =>
      String(c[0]).includes(`/sources/${SOURCE}/comparison`),
    ),
  ).toBe(true);
  expect(
    fetcher.mock.calls.some((c) =>
      String(c[0]).includes("/sources/later-source/comparison"),
    ),
  ).toBe(false);
});
it("does not show findings from a run in a different case", async () => {
  history.replaceState(null, "", `/?case=${CASE}&run=${RUN}`);
  const fetcher = mockServer({ foreign: true });
  render(<UserApp />);
  await screen.findByText(/gehört zu einem anderen Fall/);
  expect(fetcher.mock.calls.some((c) => String(c[0]).endsWith("/export"))).toBe(
    false,
  );
});
it("shows a controlled failure without pretending a report is complete", async () => {
  history.replaceState(null, "", `/?case=${CASE}&run=${RUN}`);
  mockServer({ status: "budget_exceeded" });
  render(<UserApp />);
  await screen.findByRole("heading", {
    name: "Diese Untersuchung benötigt Aufmerksamkeit.",
  });
  expect(
    screen.queryByRole("button", { name: "Bericht herunterladen" }),
  ).toBeNull();
  expect(
    screen.getByRole("button", { name: /Weitere Frage stellen/ }),
  ).toBeTruthy();
});
it("pauses and resumes the selected investigation through the existing control API", async () => {
  history.replaceState(null, "", `/?case=${CASE}&run=${RUN}`);
  const fetcher = mockServer({ status: "running" });
  render(<UserApp />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Pausieren" }),
  );
  await screen.findByRole("heading", { name: "Bereit für deine Frage." });
  await userEvent.click(
    screen.getByRole("button", { name: "Untersuchung fortsetzen" }),
  );
  await screen.findByRole("heading", { name: "Belege werden geprüft." });
  expect(
    fetcher.mock.calls.some(
      (c) => String(c[0]).endsWith("/pause") && c[1]?.method === "POST",
    ),
  ).toBe(true);
  expect(
    fetcher.mock.calls.some(
      (c) => String(c[0]).endsWith("/resume") && c[1]?.method === "POST",
    ),
  ).toBe(true);
});
it("continues a legacy token stop in the same investigation without reuploading", async () => {
  history.replaceState(null, "", `/?case=${CASE}&run=${RUN}`);
  const fetcher = mockServer({ status: "budget_exceeded", tokenStop: true });
  render(<UserApp />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Untersuchung fortsetzen" }),
  );
  await screen.findByRole("heading", { name: "Belege werden geprüft." });
  const call = fetcher.mock.calls.find(
    (c) => String(c[0]).endsWith("/continue") && c[1]?.method === "POST",
  );
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ additional_tokens: 0 });
  expect(
    fetcher.mock.calls.some(
      (c) => c[0] === "/api/cases" && c[1]?.method === "POST",
    ),
  ).toBe(false);
  expect(new URLSearchParams(location.search).get("run")).toBe(RUN);
});
it("offers bounded extra capacity only when token recovery is permitted", () => {
  const limited = {
    ...run,
    status: "budget_exceeded",
    tokens: 32768,
    error: {
      code: "budget_exceeded",
      message: "Token limit",
      resource: "tokens",
    },
  };
  expect(tokenContinuation(limited)).toBe(32768);
  expect(
    tokenContinuation({
      ...limited,
      tokens: 131072,
      limits: { ...run.limits, max_total_tokens: 131072 },
    }),
  ).toBeNull();
  expect(
    tokenContinuation({ ...limited, model_calls: run.limits.max_model_calls }),
  ).toBeNull();
});
it("starts a fresh investigation without silently reusing the previous case files", async () => {
  history.replaceState(null, "", `/?case=${CASE}&run=${RUN}`);
  mockServer();
  render(<UserApp />);
  await screen.findByRole("heading", {
    name: "Fehlausschuss stieg am stärksten bei S04",
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Engineering Intelligence Lab" }),
  );
  await screen.findByRole("heading", {
    name: "Was möchtest du untersuchen?",
  });
  expect(screen.queryByText("inspection.csv")).toBeNull();
  expect(
    screen.queryByRole("checkbox", {
      name: /Ich bestätige, dass diese Dateien/,
    }),
  ).toBeNull();
  expect(location.search).toBe("");
});
it("recovers a lost upload response by content hash rather than trusting a matching filename", async () => {
  const file = new File(["x"], "renamed.csv", { type: "text/csv" });
  const fetcher = vi.fn(
    async (input: string, _init?: RequestInit) =>
      new Response(
        JSON.stringify(
          input === `/api/cases/${CASE}` ? { sources: [source] } : run,
        ),
      ),
  );
  vi.stubGlobal("fetch", fetcher);
  const onUploaded = vi.fn();
  await startUserInvestigation({
    caseId: CASE,
    question: "Compare",
    files: [{ key: "x", name: file.name, size: 1, file }],
    policy: "synthetic",
    onCase: vi.fn(),
    onProgress: vi.fn(),
    onUploaded,
  });
  expect(
    fetcher.mock.calls.some(
      (c) => c[0].endsWith("/sources") && c[1]?.method === "POST",
    ),
  ).toBe(false);
  expect(onUploaded).toHaveBeenCalledWith("x", source);
});
it("validates files and keeps untrusted markup escaped in the readable download", () => {
  expect(() => validateFiles([], [new File(["x"], "program.exe")])).toThrow(
    "CSV- oder PDF",
  );
  const hostile = {
    ...report,
    answer: "<script>alert(1)</script>",
    citations: [
      {
        citation_id: `csv:${SOURCE}:r0`,
        kind: "csv",
        filename: "<img src=x>",
        sha256: "abc",
        source_id: SOURCE,
        row: { row_id: "<iframe>" },
      },
    ],
  };
  const html = userReport(run, hostile, comparison, "<b>input</b>");
  expect(html).not.toContain("<script>");
  expect(html).not.toContain("<img src=x>");
  expect(html).toContain("&lt;script&gt;");
  expect(html).toContain("S04");
  expect(readableAnswer(`See csv:${SOURCE}:r0.`, hostile.citations)).toBe(
    "See Quelle 1.",
  );
});
