import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./SiemensHelp";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});

it("diagnostic search sends only the submitted public question", async () => {
  history.replaceState(
    null,
    "",
    "/?view=advanced&page=siemens&case=private-case&run=private-run",
  );
  const fetcher = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        question: "OB1 cycle time",
        summary: "<script>untrusted</script>",
        curated_references: [
          {
            title: "Reviewed cycle manual",
            url: "https://docs.tia.siemens.cloud/r/manual",
            tia_version: "V20",
            edition: "06/2025",
            language: "en-US",
            kind: "curated_manual",
          },
        ],
        sources: [
          {
            title: "Manual",
            url: "https://support.industry.siemens.com/manual",
            description: "Read this",
            kind: "content",
          },
          {
            title: "Attack",
            url: "javascript:alert(1)",
            description: "bad",
            kind: "content",
          },
        ],
        retrieved_at: "2026-10-29T10:00:00Z",
        connection_verified: true,
        server_version: "test",
        limitations: "Verify the CPU version.",
      }),
      { status: 200 },
    ),
  );
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  expect(fetcher).not.toHaveBeenCalled();
  await userEvent.type(
    screen.getByRole("textbox", { name: "Your SPS / PLC question" }),
    "OB1 cycle time",
  );
  await userEvent.click(screen.getByRole("button", { name: "Search Siemens" }));
  await screen.findByText("Siemens-generated search summary");
  expect(fetcher).toHaveBeenCalledTimes(1);
  const [path, init] = fetcher.mock.calls[0];
  expect(path).toBe("/api/knowledge/siemens/search");
  expect(JSON.parse(init.body)).toEqual({ question: "OB1 cycle time" });
  expect(screen.getByText("<script>untrusted</script>")).toBeTruthy();
  expect(document.querySelector("script")).toBeNull();
  expect(screen.queryByRole("link", { name: "Attack" })).toBeNull();
  expect(
    screen
      .getByRole("link", { name: "Reviewed cycle manual" })
      .getAttribute("href"),
  ).toBe("https://docs.tia.siemens.cloud/r/manual");
  expect(
    screen.getByRole("link", { name: "Manual" }).getAttribute("rel"),
  ).toContain("noreferrer");
});

it("handles unavailable search and empty results without fabricating an answer", async () => {
  history.replaceState(null, "", "/?view=advanced&page=siemens");
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Siemens unavailable" }), {
        status: 503,
      }),
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          question: "OB1 cycle time",
          summary: "",
          sources: [],
          retrieved_at: "2026-10-29T10:00:00Z",
          connection_verified: true,
          limitations: "Coverage is incomplete.",
        }),
        { status: 200 },
      ),
    );
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: "OB1 cycle time" }));
  expect(fetcher).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Search Siemens" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Siemens unavailable",
  );
  await userEvent.click(screen.getByRole("button", { name: "Search Siemens" }));
  await screen.findByText(/No eligible Siemens sources/);
  expect(screen.queryByText("Siemens-generated search summary")).toBeNull();
});
