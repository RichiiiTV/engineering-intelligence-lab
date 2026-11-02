import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import CatalogAdmin from "./CatalogAdmin";
import { setLanguage } from "./i18n";
import { displayNotice } from "./locale";

beforeEach(() => {
  vi.useFakeTimers();
  setLanguage("de");
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
async function load(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body))),
  );
  render(<CatalogAdmin />);
  await act(async () => {
    for (let i = 0; i < 15; i++) await Promise.resolve();
  });
}
const corpus = {
  machines: [
    {
      id: "voron",
      name: "Voron 2.4",
      identity_kind: "product_family",
      documents: [
        {
          id: "manual",
          filename: "manual.md",
          active: true,
          passages: 63,
          indexed_passages: 63,
          assignment_basis: "source-identity",
        },
      ],
    },
    {
      id: "unknown",
      name: "Generated unidentified source",
      identity_kind: "unknown",
      documents: [
        {
          id: "partial",
          filename: "partial.md",
          active: false,
          passages: 3,
          indexed_passages: 1,
          assignment_basis: "unassigned",
        },
      ],
    },
  ],
  jobs: [
    {
      id: "one",
      filename: "manual.md",
      status: "completed",
      phase: "ready",
      progress: 100,
      document_id: "manual",
      assigned_machine_id: "voron",
    },
    {
      id: "two",
      filename: "partial.md",
      status: "completed",
      phase: "ready",
      progress: 100,
      document_id: "partial",
      assigned_machine_id: "unknown",
    },
    {
      id: "three",
      filename: "queued.md",
      status: "queued",
      phase: "queued",
      progress: 0,
    },
    {
      id: "four",
      filename: "failed.md",
      status: "failed",
      phase: "indexing",
      progress: 40,
    },
    {
      id: "five",
      filename: "discarded.md",
      status: "canceled",
      phase: "discarded",
      progress: 0,
    },
  ],
};

it("summarizes completed, active and actionable uploads with source index counts", async () => {
  await load(corpus);
  const summary = screen.getByLabelText("Upload-Übersicht");
  expect(summary.textContent).toBe(
    "Abgeschlossen: 2 · In Arbeit: 1 · Aufmerksamkeit nötig: 1",
  );
  const job = screen
    .getAllByText("manual.md")[0]
    .closest(".machine-source") as HTMLElement;
  expect(within(job).getByText("Voron 2.4")).toBeTruthy();
  expect(job.textContent).toContain("Produktfamilie:");
  expect(job.textContent).toContain("63/63 Abschnitte indexiert · Verfügbar");
  const unknown = screen
    .getAllByText("partial.md")[0]
    .closest(".machine-source") as HTMLElement;
  expect(unknown.textContent).toContain("Identität nicht belegt:");
  expect(unknown.textContent).toContain(
    "1/3 Abschnitte indexiert · Archiviert",
  );
  expect(unknown.textContent).not.toContain("Maschine:");
});

it("keeps missing assignment results explicit and translates summaries without changing content", async () => {
  await load({ machines: [], jobs: [corpus.jobs[0]] });
  expect(screen.getByText("Zuordnungsergebnis wird geladen…")).toBeTruthy();
  act(() => setLanguage("en"));
  expect(screen.getByText("Loading the assignment result…")).toBeTruthy();
  expect(screen.getByLabelText("Upload summary").textContent).toBe(
    "Completed: 1 · In progress: 0 · Needs attention: 0",
  );
  expect(screen.getByText("manual.md")).toBeTruthy();
});

it("localizes the opaque-citation vendor warning while preserving its English text", () => {
  const warning =
    "Vendor identification is not established by the human question or source text; citation IDs are opaque.";
  expect(displayNotice(warning)).toContain(
    "Quellenkennungen enthalten keine Herstellerinformation",
  );
  setLanguage("en");
  expect(displayNotice(warning)).toBe(warning);
});
