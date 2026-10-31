import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdminWorkspace from "./AdminWorkspace";
import {
  LibraryChooser,
  LibraryReferences,
  type LibrarySelection,
} from "./KnowledgeLibrary";
import { readableAnswer } from "./userFlow";
import { userReport } from "./userReport";
import type { EvidenceReport, Run } from "./types";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const document = {
  id: "11111111-1111-4111-8111-111111111111",
  title: "Timing guide",
  filename: "guide.txt",
  family: "Demo",
  version: "v1",
  license_note: "CC0",
  data_policy: "synthetic",
  active: true,
  indexed_passages: 2,
  passages: 2,
};

it("selects a shared library by default and lets the user narrow or disable it", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            documents: [
              document,
              { ...document, id: "disabled", active: false },
            ],
          }),
        ),
    ),
  );
  let selection: LibrarySelection = { enabled: true };
  function Form() {
    const [value, setValue] = useState(selection);
    return (
      <LibraryChooser
        value={value}
        busy={false}
        onChange={(next) => {
          selection = next;
          setValue(next);
        }}
      />
    );
  }
  render(<Form />);
  await userEvent.click(screen.getByText("Wissensbibliothek"));
  const source = await screen.findByRole("checkbox", { name: /Timing guide/ });
  expect((source as HTMLInputElement).checked).toBe(true);
  await userEvent.click(source);
  expect(selection.documentIds).toEqual([]);
  await userEvent.click(
    screen.getByRole("checkbox", {
      name: "Dokumentbibliothek des Arbeitsbereichs durchsuchen",
    }),
  );
  expect(selection.enabled).toBe(false);
});

it("renders scoped library passages and escapes document text in the report", async () => {
  const cid = `kb:${document.id}:p1:c0`;
  const report = {
    answer: `A sourced answer [${cid}]`,
    citations: [],
    source_snapshot: [],
    citation_checks: {
      unresolved: [],
      not_returned_by_tools: [],
      malformed: [],
      has_answer_citations: false,
    },
    uncertainty: { limitations: [] },
    library_snapshot: [document],
    library_citations: [
      {
        ...document,
        citation_id: cid,
        page: 1,
        text: "<script>untrusted()</script>",
        cited_in_answer: true,
      },
    ],
    library_retrieval: { method: "hybrid", semantic_available: true },
  } as EvidenceReport;
  render(<LibraryReferences report={report} runId="my-run" />);
  await userEvent.click(screen.getByText(/Bibliotheksquelle 1:/));
  expect(screen.getByText("<script>untrusted()</script>")).toBeTruthy();
  expect(
    screen
      .getByRole("link", { name: "Quelldokument herunterladen" })
      .getAttribute("href"),
  ).toBe(`/api/investigations/my-run/library/documents/${document.id}/file`);
  expect(readableAnswer(report.answer, report.library_citations!)).toContain(
    "Bibliotheksquelle 1",
  );
  const html = userReport(
    { id: "run", question: "Test", status: "completed" } as Run,
    report,
    null,
    "",
  );
  expect(html).toContain("Abschnitte der Wissensbibliothek");
  expect(html).toContain("&lt;script&gt;");
  expect(html).not.toContain("<script>untrusted()");
});

it("shows user permissions and sends explicit changes while protecting the current admin", async () => {
  const calls: { path: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        calls.push({
          path,
          body: init.body ? JSON.parse(String(init.body)) : null,
        });
        return new Response("{}");
      }
      if (path.startsWith("/api/auth/users"))
        return new Response(
          JSON.stringify({
            users: [
              {
                id: "self",
                username: "owner",
                role: "admin",
                active: true,
                sessions: 1,
              },
              {
                id: "other",
                username: "member",
                role: "member",
                active: true,
                sessions: 2,
              },
            ],
            next_offset: null,
          }),
        );
      return new Response(JSON.stringify({ documents: [] }));
    }),
  );
  render(<AdminWorkspace currentUserId="self" onClose={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: "Benutzer" }));
  await screen.findByText("member");
  const disable = screen.getAllByRole("button", { name: "Konto deaktivieren" });
  expect((disable[0] as HTMLButtonElement).disabled).toBe(true);
  await userEvent.click(disable[1]);
  expect(calls).toContainEqual({
    path: "/api/auth/users/other/update",
    body: { active: false },
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Als Administrator festlegen" }),
  );
  expect(calls).toContainEqual({
    path: "/api/auth/users/other/update",
    body: { role: "admin" },
  });
});

it("displays audit integrity and paginates with the returned cursor", async () => {
  const paths: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      paths.push(path);
      if (path.startsWith("/api/admin/audit"))
        return new Response(
          JSON.stringify({
            events: [
              {
                id: path.includes("after=7") ? 8 : 7,
                at: 1,
                actor: "owner",
                kind: "user_updated",
                details: { active: false },
                entry_hash: "hash",
              },
            ],
            next_after: path.includes("after=7") ? null : 7,
            integrity: { valid: true, checked: 8 },
          }),
        );
      return new Response(JSON.stringify({ documents: [] }));
    }),
  );
  render(<AdminWorkspace currentUserId="self" onClose={() => {}} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Audit-Protokoll" }),
  );
  await screen.findByText(/Audit-Kette verifiziert/);
  await userEvent.click(
    screen.getByRole("button", { name: "Weitere Audit-Ereignisse laden" }),
  );
  expect(paths.some((path) => path.includes("after=7"))).toBe(true);
  expect(await screen.findByText("#8 user_updated")).toBeTruthy();
});
