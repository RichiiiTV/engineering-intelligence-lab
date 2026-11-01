import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import SafeAnswer from "./SafeAnswer";
import { setLanguage } from "./i18n";

afterEach(cleanup);

it("separates headings, adjacent lists and paragraphs without requiring blank lines", () => {
  render(
    <SafeAnswer
      text={
        "### Findings\n- First observation\n- Second observation\n### Next checks\n1. Read the manual\n2. Compare the log\nKeep uncertainty explicit."
      }
    />,
  );
  expect(screen.getByRole("heading", { name: "Findings" }).textContent).toBe(
    "Findings",
  );
  expect(screen.getByRole("heading", { name: "Next checks" }).textContent).toBe(
    "Next checks",
  );
  expect(screen.getAllByRole("list").map((list) => list.tagName)).toEqual([
    "UL",
    "OL",
  ]);
  expect(screen.getAllByRole("listitem").length).toBe(4);
  expect(screen.getByText("Keep uncertainty explicit.").tagName).toBe("P");
});

it("preserves citation controls and escaped source markup in mixed blocks", () => {
  setLanguage("de");
  const open = vi.fn();
  const { container } = render(
    <SafeAnswer
      text={
        "### Evidence\n- Read [kb:doc:p1:c0]\n<script>unsafe()</script>\n![remote](https://external.invalid/image)\nUnknown [kb:missing:p1:c0]\n```txt\n# untouched code\n```"
      }
      references={[{ citation_id: "kb:doc:p1:c0", title: "Document" }]}
      onOpenSource={open}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "[Quelle 1]" }));
  expect(open).toHaveBeenCalledWith("kb:doc:p1:c0");
  expect(container.querySelector("script,img,iframe")).toBeNull();
  expect(screen.getByText(/Unknown \[kb:missing/)).toBeTruthy();
  expect(container.querySelector("pre code")?.textContent).toContain(
    "# untouched code",
  );
  expect(screen.getAllByRole("button").length).toBe(1);
});

it("only activates whitelisted Siemens URLs", () => {
  const { container } = render(
    <SafeAnswer
      text="### References\n- [siemens:approved]\n- [siemens:unsafe]"
      references={[
        {
          citation_id: "siemens:approved",
          url: "https://support.industry.siemens.com/example",
        },
        {
          citation_id: "siemens:unsafe",
          url: "https://external.invalid/collect",
        },
      ]}
    />,
  );
  expect(screen.getAllByRole("link").length).toBe(1);
  expect(screen.getByRole("link").getAttribute("rel")).toBe(
    "noopener noreferrer",
  );
  expect(container.textContent).toContain("[siemens:unsafe]");
});
