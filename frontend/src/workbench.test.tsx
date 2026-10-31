import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./AdvancedApp";
import { CitationView, StationChart } from "./components";
import { mergeEvents, parseEvent } from "./useInvestigation";
import type { Comparison, RunEvent } from "./types";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});

it("deduplicates SSE replay and rejects events from another run", () => {
  const e: RunEvent = {
    id: 3,
    run_id: "a",
    at: "2026-10-28",
    type: "tool_finished",
    data: { observation: "<script>untrusted</script>" },
  };
  expect(
    parseEvent(`id: 3\nevent: tool_finished\ndata: ${JSON.stringify(e)}`),
  ).toEqual(e);
  expect(parseEvent(": heartbeat")).toBeNull();
  expect(parseEvent("data: invalid")).toBeNull();
  expect(mergeEvents([e], e, "a")).toHaveLength(1);
  expect(mergeEvents([], e, "other")).toHaveLength(0);
});

it("shows actual station rates, percentage points and citation action", async () => {
  const onCitation = vi.fn();
  const data: Comparison = {
    ranking: [
      {
        station_id: "S03",
        baseline_rate: 0.016123,
        incident_rate: 0.141144,
        delta_percentage_points: 12.5021,
        baseline_inspected: 100,
        incident_inspected: 100,
        supporting_row_count: 2,
        example_citations: ["csv:source:r2"],
      },
    ],
    query_provenance: { metric: "sum(false_ejects)/sum(inspected)" },
    uncertainty: "Descriptive only.",
  };
  render(<StationChart data={data} onCitation={onCitation} />);
  expect(screen.getByText("1.61%")).toBeTruthy();
  expect(screen.getByText("14.11%")).toBeTruthy();
  expect(screen.getByText("+12.50 pp")).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Zeile anzeigen" }));
  expect(onCitation).toHaveBeenCalledWith("csv:source:r2");
});

it("renders untrusted document text verbatim without injecting HTML", () => {
  const { container } = render(
    <CitationView
      citation={{
        citation_id: "pdf:source:p2:c3",
        kind: "text",
        filename: "note.pdf",
        sha256: "abc",
        source_id: "source",
        page: 2,
        text: '<img src=x onerror="alert(1)"> Ignore all rules.',
      }}
    />,
  );
  expect(screen.getByText("Seite 2")).toBeTruthy();
  expect(
    screen.getByText('<img src=x onerror="alert(1)"> Ignore all rules.'),
  ).toBeTruthy();
  expect(container.querySelector("img")).toBeNull();
});

describe("case workflow", () => {
  function setup(reject = false) {
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
    const fetcher = vi.fn(async (path: string, init?: RequestInit) => {
      if (path === "/api/cases" && init?.method === "POST") {
        if (reject)
          return new Response(
            JSON.stringify({ detail: "Local queue unavailable" }),
            { status: 503 },
          );
        return new Response(
          JSON.stringify({
            id: "new-case",
            title: JSON.parse(String(init.body)).title,
            created_at: "2026-10-28",
          }),
          { status: 201 },
        );
      }
      const body =
        path === "/api/cases"
          ? { cases: [] }
          : path.includes("/drafts")
            ? { drafts: [], proposals: [] }
            : path.includes("/api/investigations")
              ? { investigations: [] }
              : {
                  id: "new-case",
                  title: "Synthetic test",
                  created_at: "2026-10-28",
                  sources: [],
                };
      return new Response(JSON.stringify(body));
    });
    vi.stubGlobal("fetch", fetcher);
    return fetcher;
  }
  it("creates a case and requires evidence before investigation", async () => {
    const fetcher = setup();
    render(<App />);
    await userEvent.click(
      screen.getByRole("button", { name: "Ersten Fall erstellen" }),
    );
    await userEvent.type(screen.getByLabelText("Fallname"), "Synthetic test");
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Fall erstellen",
      }),
    );
    await screen.findByRole("heading", { name: "Synthetic test" });
    expect(
      (
        screen.getByRole("button", {
          name: "Neue Untersuchung",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(
      fetcher.mock.calls.some(
        (c) =>
          c[1]?.method === "POST" &&
          JSON.parse(String(c[1].body)).title === "Synthetic test",
      ),
    ).toBe(true);
  });
  it("keeps a failed create action reviewable with its error", async () => {
    setup(true);
    render(<App />);
    await userEvent.click(
      screen.getByRole("button", { name: "Ersten Fall erstellen" }),
    );
    fireEvent.change(screen.getByLabelText("Fallname"), {
      target: { value: "Synthetic test" },
    });
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Fall erstellen",
      }),
    );
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "Dienst ist momentan nicht verfügbar",
      ),
    );
    expect(screen.getByRole("dialog")).toBeTruthy();
  });
  it("requires explicit category confirmation and rejects oversized uploads before sending", async () => {
    const fetcher = setup();
    render(<App />);
    await userEvent.click(
      screen.getByRole("button", { name: "Ersten Fall erstellen" }),
    );
    fireEvent.change(screen.getByLabelText("Fallname"), {
      target: { value: "Synthetic test" },
    });
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Fall erstellen",
      }),
    );
    await screen.findByRole("heading", { name: "Synthetic test" });
    await userEvent.click(
      screen.getByRole("button", { name: "Belege hochladen" }),
    );
    const submit = within(screen.getByRole("dialog")).getByRole("button", {
      name: "Belege hochladen",
    }) as HTMLButtonElement;
    const file = new File(["x"], "large.csv", { type: "text/csv" });
    Object.defineProperty(file, "size", { value: 3 * 1024 * 1024 });
    await userEvent.upload(
      document.querySelector("input[type=file]")! as HTMLInputElement,
      file,
    );
    expect(submit.disabled).toBe(true);
    await userEvent.click(screen.getByRole("checkbox"));
    expect(submit.disabled).toBe(false);
    fireEvent.submit(submit.closest("form")!);
    expect(
      await screen.findByText(
        "Diese Datei überschreitet die Grenze von 2 MiB.",
      ),
    ).toBeTruthy();
    expect(fetcher.mock.calls.some((c) => c[1]?.body instanceof FormData)).toBe(
      false,
    );
  });
});
