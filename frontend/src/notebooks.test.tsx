import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NotebookPanel from "./NotebookPanel";
import SafeAnswer from "./SafeAnswer";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});

it("renders source links and code safely without interpreting HTML or URLs", async () => {
  const user = userEvent.setup(),
    scroll = vi.fn();
  const cid = "kb:11111111-1111-4111-8111-111111111111:p1:c0";
  render(
    <>
      <SafeAnswer
        text={
          "**Check** [" +
          cid +
          "]\n\n```st\nmotor := FALSE;\n```\n\n<img src=x onerror=alert(1)> [bad](javascript:alert(1))"
        }
        references={[{ citation_id: cid }]}
      />
      <details id={"source-" + cid}>
        <summary>Passage</summary>Source data
      </details>
    </>,
  );
  const details = screen.getByText("Passage")
    .parentElement as HTMLDetailsElement;
  details.scrollIntoView = scroll;
  await user.click(screen.getByRole("button", { name: "[Source 1]" }));
  expect(details.open).toBe(true);
  expect(scroll).toHaveBeenCalled();
  expect(document.querySelector("img")).toBeNull();
  expect(screen.queryByRole("link")).toBeNull();
  expect(screen.getByText("motor := FALSE;")).toBeTruthy();
});

it("keeps a rejected follow-up and sends only the separately entered Siemens question", async () => {
  history.replaceState(null, "", "/?page=machines&machine=m&notebook=n");
  const requests: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path.endsWith("/questions")) {
        requests.push(JSON.parse(String(init?.body)));
        return new Response(
          JSON.stringify({ detail: "Controlled queue failure" }),
          { status: 409 },
        );
      }
      return new Response(
        JSON.stringify(
          path.endsWith("/notebooks")
            ? { notebooks: [] }
            : {
                id: "n",
                title: "Stops",
                document_ids: [],
                library_document_ids: [],
                revision: 1,
                turns: [],
              },
        ),
      );
    }),
  );
  const user = userEvent.setup();
  render(<NotebookPanel machineId="m" sources={[]} />);
  const question = await screen.findByRole("textbox", {
    name: "Ask about this machine",
  });
  await user.type(question, "Our private line fails");
  await user.click(
    screen.getByText("Check Siemens public documentation (optional)"),
  );
  await user.click(
    screen.getByRole("checkbox", {
      name: "Use this public question for this answer",
    }),
  );
  await user.type(
    screen.getByRole("textbox", { name: "Public Siemens question" }),
    "S7-1200 cycle manual",
  );
  await user.click(screen.getByRole("button", { name: /Ask question/ }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect((question as HTMLTextAreaElement).value).toBe(
    "Our private line fails",
  );
  expect(requests[0].siemens).toEqual({ question: "S7-1200 cycle manual" });
  await user.click(screen.getByRole("button", { name: /Ask question/ }));
  expect(requests[1].request_id).toBe(requests[0].request_id);
});
