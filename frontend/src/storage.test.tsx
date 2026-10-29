import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StorageSettings from "./StorageSettings";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("requires review and exact content-bound confirmation before permanent deletion", async () => {
  const calls: { path: string; body: unknown }[] = [];
  const plan = {
    id: "plan-id",
    sha256: "a".repeat(64),
    expires_at: "2099-01-01T00:00:00Z",
    cases: [{ id: "case-id", title: "Old synthetic case" }],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      calls.push({
        path,
        body: init?.body ? JSON.parse(String(init.body)) : null,
      });
      const result =
        path === "/api/retention/plan"
          ? plan
          : path.startsWith("/api/cases?")
            ? { cases: [], next_offset: null }
            : { status: "completed" };
      return new Response(JSON.stringify(result));
    }),
  );
  render(<StorageSettings admin={false} />);
  await userEvent.click(
    await screen.findByRole("button", {
      name: "Review Trash older than 90 days",
    }),
  );
  const approve = await screen.findByRole("button", {
    name: "Approve reviewed deletion",
  });
  expect(approve.hasAttribute("disabled")).toBe(true);
  expect(calls.some((c) => c.path === "/api/retention/apply")).toBe(false);
  await userEvent.type(
    screen.getByLabelText(/Type PERMANENTLY/),
    "PERMANENTLY PURGE REVIEWED TRASH",
  );
  await userEvent.click(approve);
  await screen.findByRole("status");
  expect(calls.find((c) => c.path === "/api/retention/apply")?.body).toEqual({
    plan_id: plan.id,
    expected_sha256: plan.sha256,
    confirmation: "PERMANENTLY PURGE REVIEWED TRASH",
  });
  expect(
    screen.queryByRole("button", { name: "Create verified backup" }),
  ).toBeNull();
});
