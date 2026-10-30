import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MachineApp from "./MachineApp";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  history.replaceState(null, "", "/");
});
it("shows automatic groups with explicit machine choices", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            groups: [
              {
                id: "group",
                label: "Related machines",
                indexed: true,
                machines: [
                  { id: "a", name: "Packaging A", family: "Demo" },
                  { id: "b", name: "Packaging B", family: "Demo" },
                ],
              },
            ],
          }),
        ),
    ),
  );
  render(<MachineApp />);
  expect(await screen.findByText("AUTOMATIC SIMILARITY GROUP")).toBeTruthy();
  expect(screen.getByRole("button", { name: /Packaging A/ })).toBeTruthy();
  expect(screen.getByText(/do not combine investigation sources/)).toBeTruthy();
});
it("retains machine creation input after a server rejection", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      path === "/api/machines/groups"
        ? new Response(JSON.stringify({ groups: [] }))
        : new Response(JSON.stringify({ detail: "Machine capacity reached" }), {
            status: 409,
          }),
    ),
  );
  const user = userEvent.setup();
  render(<MachineApp />);
  await user.click(await screen.findByRole("button", { name: "Add machine" }));
  const input = screen.getByRole("textbox", { name: "Machine name" });
  await user.type(input, "Line 3");
  await user.click(
    screen.getByRole("button", { name: "Create private workspace" }),
  );
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect((input as HTMLInputElement).value).toBe("Line 3");
});
