import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./UserApp";
import { userReport } from "./userReport";
import type { Run, EvidenceReport, Source } from "./types";

const ID = "11111111-1111-4111-8111-111111111111",
  CASE = "22222222-2222-4222-8222-222222222222",
  SOURCE = "33333333-3333-4333-8333-333333333333";
const QUERY = "How does OB1 work in S7-1500?";
const CID = `siemens:${ID}:r0`;
const run: Run = {
  id: ID,
  case_id: null,
  chat_mode: true,
  question: QUERY,
  status: "completed",
  created_at: "2026-10-29T10:00:00Z",
  model: "test",
  model_calls: 2,
  tool_calls: 1,
  tokens: 200,
  steps: 5,
  elapsed_seconds: 2,
  attempt_started_at: null,
  source_ids: [],
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
  result: {
    answer: `Review the cycle manual [${CID}].`,
    warning: "Verify exact firmware.",
  },
};
const source: Source = {
  id: SOURCE,
  filename: "inspection.csv",
  kind: "csv",
  sha256: "a".repeat(64),
  size: 100,
  data_policy: "synthetic",
};
const report: EvidenceReport = {
  answer: run.result!.answer,
  citations: [],
  source_snapshot: [],
  citation_checks: {
    unresolved: [],
    not_returned_by_tools: [],
    malformed: [],
    has_answer_citations: false,
  },
  uncertainty: { limitations: ["Exact firmware applicability is unverified."] },
  integrations: {
    siemens: {
      enabled: true,
      outbound_query: QUERY,
      status: "finished",
      remote_search_status: "completed",
      connection_verified: true,
      version_notice: "Check exact CPU and firmware.",
    },
  },
  external_references: [
    {
      citation_id: CID,
      title: "Cycle and response times",
      url: "https://docs.tia.siemens.cloud/r/manual",
      kind: "curated_manual",
      tia_version: "V20",
      cited_in_answer: true,
    },
  ],
  external_reference_checks: {
    unresolved: [],
    technical_claims_verified: false,
  },
};

beforeEach(() => {
  history.replaceState(null, "", "/");
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});

function server(withCase = false) {
  let payload: Record<string, unknown> | null = null;
  const json = (value: unknown) => new Response(JSON.stringify(value));
  const fetcher = vi.fn(
    async (input: string | URL | Request, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/cases")
        return json({
          cases: withCase
            ? [{ id: CASE, title: "File case", created_at: run.created_at }]
            : [],
          next_offset: null,
        });
      if (path === `/api/cases/${CASE}`)
        return json({
          id: CASE,
          title: "File case",
          created_at: run.created_at,
          sources: [source],
        });
      if (path === "/api/investigations" && init?.method === "POST") {
        payload = JSON.parse(String(init.body));
        return json({
          ...run,
          question: payload!.question,
          case_id: withCase ? CASE : null,
          chat_mode: !withCase,
        });
      }
      if (path === "/api/investigations")
        return json({
          investigations: payload
            ? [
                {
                  ...run,
                  question: payload.question,
                  case_id: withCase ? CASE : null,
                  chat_mode: !withCase,
                },
              ]
            : [],
          next_offset: null,
        });
      if (path === `/api/investigations/${ID}`)
        return json({
          ...run,
          question: payload?.question || QUERY,
          case_id: withCase ? CASE : null,
          chat_mode: !withCase,
          source_ids: withCase ? [SOURCE] : [],
        });
      if (path.includes("/events?"))
        return new Response("", {
          headers: { "Content-Type": "text/event-stream" },
        });
      if (path.endsWith("/export"))
        return json(
          payload?.siemens
            ? { ...report, source_snapshot: withCase ? [source] : [] }
            : {
                ...report,
                integrations: { siemens: null },
                external_references: [],
              },
        );
      if (path.endsWith("/comparison"))
        return json({
          ranking: [],
          query_provenance: { source_id: SOURCE },
          uncertainty: "No comparison.",
        });
      throw new Error(`Unexpected request ${path}`);
    },
  );
  vi.stubGlobal("fetch", fetcher);
  return { fetcher, getPayload: () => payload };
}

it("asks a Siemens question in the normal composer and shows its answer/references inline", async () => {
  const api = server();
  render(<App />);
  await userEvent.type(screen.getByLabelText("Your question"), QUERY);
  expect(
    (
      screen.getByRole("checkbox", {
        name: /Use Siemens public documentation/,
      }) as HTMLInputElement
    ).checked,
  ).toBe(true);
  expect(screen.queryByRole("link", { name: "SPS help" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText("Answer ready");
  const references = await screen.findByRole("region", {
    name: "Siemens documentation",
  });
  expect(
    within(references)
      .getByRole("link", { name: /Cycle and response times/ })
      .getAttribute("href"),
  ).toBe("https://docs.tia.siemens.cloud/r/manual");
  expect(
    screen.getByText(/Review the cycle manual \[Siemens source 1\]/),
  ).toBeTruthy();
  expect(api.getPayload()).toMatchObject({
    question: QUERY,
    chat_mode: true,
    siemens: { question: QUERY },
  });
  expect(api.getPayload()).not.toHaveProperty("case_id");
  expect(
    api.fetcher.mock.calls.some(([path]) =>
      String(path).includes("/knowledge/siemens"),
    ),
  ).toBe(false);
  await userEvent.click(
    within(
      screen.getByRole("navigation", { name: "Main navigation" }),
    ).getByRole("button", { name: "My investigations" }),
  );
  expect(
    await screen.findByRole("button", { name: new RegExp("How does OB1") }),
  ).toBeTruthy();
});

it("keeps file questions local and requires a separate public query before enabling lookup", async () => {
  history.replaceState(null, "", `/?case=${CASE}`);
  const api = server(true);
  render(<App />);
  await screen.findByText("inspection.csv");
  await userEvent.type(
    screen.getByLabelText("Your question"),
    "PRIVATE station log: why did the PLC stop?",
  );
  const toggle = screen.getByRole("checkbox", {
    name: /Use Siemens public documentation/,
  }) as HTMLInputElement;
  expect(toggle.checked).toBe(false);
  await userEvent.click(toggle);
  expect(
    (
      screen.getByRole("button", {
        name: "Investigate",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  await userEvent.type(screen.getByLabelText("Public Siemens question"), QUERY);
  await userEvent.click(screen.getByRole("button", { name: "Investigate" }));
  await screen.findByText("Investigation complete");
  expect(api.getPayload()).toMatchObject({
    case_id: CASE,
    question: "PRIVATE station log: why did the PLC stop?",
    siemens: { question: QUERY },
  });
  expect(JSON.stringify(api.getPayload()?.siemens)).not.toContain("PRIVATE");
  expect(JSON.stringify(api.getPayload()?.siemens)).not.toContain(
    "inspection.csv",
  );
});

it("supports opting out and routes old SPS links to the normal composer", async () => {
  history.replaceState(null, "", "/?page=siemens");
  const api = server();
  render(<App />);
  expect(
    screen.getByRole("heading", {
      name: "What would you like to investigate?",
    }),
  ).toBeTruthy();
  await userEvent.type(screen.getByLabelText("Your question"), QUERY);
  await userEvent.click(
    screen.getByRole("checkbox", { name: /Use Siemens public documentation/ }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText("Answer ready");
  expect(api.getPayload()).not.toHaveProperty("siemens");
  expect(
    screen.queryByRole("region", { name: "Siemens documentation" }),
  ).toBeNull();
});

it("preserves safe Siemens references in downloaded reports", () => {
  const html = userReport(
    run,
    {
      ...report,
      external_references: [
        ...report.external_references!,
        {
          citation_id: "bad",
          title: "Attack",
          url: "javascript:alert(1)",
          kind: "content",
        },
      ],
    },
    null,
    "",
  );
  const doc = new DOMParser().parseFromString(html, "text/html");
  expect(
    doc.querySelector('a[href="https://docs.tia.siemens.cloud/r/manual"]'),
  ).toBeTruthy();
  expect(doc.querySelector('a[href^="javascript:"]')).toBeNull();
});
