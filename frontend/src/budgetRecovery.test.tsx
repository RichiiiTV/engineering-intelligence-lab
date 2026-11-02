import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatApp from "./ChatApp";
import { setLanguage } from "./i18n";
import { tokenContinuation } from "./budgetRecovery";
import type { Run } from "./types";

vi.mock("./AuthGate", () => ({ useCurrentUser: () => ({ role: "member" }) }));
const run = {
  case_id: null,
  created_at: "2026-11-02T00:00:00Z",
  model: "offline",
  attempt_started_at: null,
  source_ids: [],
  use_mock_mcp: false,
  id: "r",
  question: "Alarm E17",
  status: "budget_exceeded",
  chat_context: { id: "c" },
  model_calls: 2,
  tool_calls: 1,
  steps: 5,
  tokens: 18731,
  elapsed_seconds: 45,
  limits: {
    max_model_calls: 5,
    max_tool_calls: 8,
    max_steps: 25,
    max_total_tokens: 32768,
    max_output_tokens: 1024,
    timeout_seconds: 120,
  },
  error: {
    code: "budget_exceeded",
    resource: "output_tokens",
    message: "Output limit",
  },
  result: {
    answer_mode: "budget_source_extract",
    answer: "Partial evidence review\n\n> Alarm E17\n\n[kb:doc:p1:c1]",
    capacity_limited: true,
    warning: "Incomplete",
    answer_contract: {
      outcome: "budget_limited",
      issues: [],
      claim_entailment: "not_verified",
    },
  },
} as Run;
beforeEach(() => {
  setLanguage("de");
  history.replaceState(null, "", "/?chat=c");
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
  setLanguage("de");
});
function server(stopped: Run, reject = false) {
  let current = stopped;
  const fetcher = vi.fn(async (path: string, init?: RequestInit) => {
    if (path.endsWith("/continue") && init?.method === "POST") {
      if (reject)
        return new Response(
          JSON.stringify({ detail: "Another run limit is exhausted" }),
          { status: 409 },
        );
      current = { ...stopped, status: "queued" };
      return new Response(JSON.stringify(current));
    }
    if (path.endsWith("/export"))
      return new Response(
        JSON.stringify({
          answer: stopped.result!.answer,
          answer_contract: stopped.result!.answer_contract,
          library_citations: [
            {
              id: "doc",
              citation_id: "kb:doc:p1:c1",
              title: "Generated guide",
              filename: "guide.txt",
              text: "Alarm E17",
              page: 1,
            },
          ],
          problem_citations: [],
          external_references: [],
        }),
      );
    return new Response(
      JSON.stringify(
        path.endsWith("/c")
          ? { id: "c", title: "Problem", turns: [current], attachments: [] }
          : { conversations: [] },
      ),
    );
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
it("shows cited partial evidence and only continues after an explicit click", async () => {
  const fetcher = server(run);
  render(<ChatApp />);
  const button = await screen.findByRole("button", {
    name: "Aus vorhandenen Belegen abschließen",
  });
  expect(screen.getByText("Partial evidence review")).toBeTruthy();
  expect(
    await screen.findByRole("button", { name: "[Quelle 1]" }),
  ).toBeTruthy();
  expect(fetcher.mock.calls.some(([p]) => p.endsWith("/continue"))).toBe(false);
  await userEvent.click(button);
  const sent = fetcher.mock.calls.find(([p]) => p.endsWith("/continue"))!;
  expect(sent[1]?.method).toBe("POST");
  expect(JSON.parse(sent[1]!.body as string)).toEqual({ additional_tokens: 0 });
  await waitFor(() =>
    expect(screen.queryByText("Partial evidence review")).toBeNull(),
  );
  expect(screen.queryByRole("button", { name: "[Quelle 1]" })).toBeNull();
});
it("asks explicitly for extra capacity at a total-token stop and preserves the preview on rejection", async () => {
  const fetcher = server(
    { ...run, tokens: 32768, error: { ...run.error!, resource: "tokens" } },
    true,
  );
  render(<ChatApp />);
  await userEvent.click(
    await screen.findByRole("button", {
      name: "Mit zusätzlicher Kapazität fortsetzen",
    }),
  );
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByText("Partial evidence review")).toBeTruthy();
  const sent = fetcher.mock.calls.find(([p]) => p.endsWith("/continue"))!;
  expect(JSON.parse(sent[1]!.body as string)).toEqual({
    additional_tokens: 32768,
  });
});
it("localizes recovery controls without translating the saved answer", async () => {
  setLanguage("en");
  server(run);
  render(<ChatApp />);
  expect(
    await screen.findByRole("button", {
      name: "Finish from existing evidence",
    }),
  ).toBeTruthy();
  expect(screen.getByText("Partial evidence review")).toBeTruthy();
  expect(screen.getByText(/No new searches will be started/)).toBeTruthy();
});
it("offers no finish action when another limit or the existing token allowance is exhausted", () => {
  expect(tokenContinuation({ ...run, tokens: 32768 })).toBeNull();
  expect(tokenContinuation({ ...run, model_calls: 5 })).toBeNull();
  expect(tokenContinuation({ ...run, tool_calls: 8 })).toBeNull();
  expect(tokenContinuation({ ...run, steps: 25 })).toBeNull();
  expect(tokenContinuation({ ...run, elapsed_seconds: 120 })).toBeNull();
  expect(
    tokenContinuation({
      ...run,
      error: { ...run.error!, resource: "provider_usage" },
    }),
  ).toBeNull();
  expect(tokenContinuation({ ...run, status: "timed_out" })).toBeNull();
});
