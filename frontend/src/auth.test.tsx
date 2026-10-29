import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AuthGate from "./AuthGate";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("hides workspace data until sign-in and clears it on sign-out", async () => {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      calls.push(path);
      if (path === "/api/auth/status")
        return new Response(JSON.stringify({ configured: true }));
      if (path === "/api/auth/me")
        return new Response(JSON.stringify({ detail: "Sign in" }), {
          status: 401,
        });
      if (path === "/api/auth/login") {
        expect(JSON.parse(String(init?.body))).toEqual({
          username: "owner",
          password: "Synthetic-test-password",
        });
        return new Response(
          JSON.stringify({
            user: { id: "u1", username: "owner", role: "admin" },
          }),
        );
      }
      return new Response(JSON.stringify({ signed_out: true }));
    }),
  );
  render(
    <AuthGate>
      <p>Private workspace data</p>
    </AuthGate>,
  );
  await screen.findByRole("button", { name: "Sign in" });
  expect(screen.queryByText("Private workspace data")).toBeNull();
  await userEvent.type(screen.getByLabelText("Username"), "owner");
  await userEvent.type(
    screen.getByLabelText("Password", { exact: true }),
    "Synthetic-test-password",
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByText("Private workspace data");
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await screen.findByRole("button", { name: "Sign in" });
  expect(screen.queryByText("Private workspace data")).toBeNull();
  expect(calls).toContain("/api/auth/logout");
});

it("requires a one-time local setup code and never stores passwords in browser storage", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path === "/api/auth/status")
        return new Response(JSON.stringify({ configured: false }));
      expect(JSON.parse(String(init?.body))).toEqual({
        username: "owner",
        password: "Synthetic-test-password",
        code: "one-time-code",
      });
      return new Response(
        JSON.stringify({
          user: { id: "u1", username: "owner", role: "admin" },
        }),
      );
    }),
  );
  render(
    <AuthGate>
      <p>Workspace</p>
    </AuthGate>,
  );
  await screen.findByLabelText("One-time setup code");
  await userEvent.type(
    screen.getByLabelText("One-time setup code"),
    "one-time-code",
  );
  await userEvent.type(screen.getByLabelText("Username"), "owner");
  await userEvent.type(
    screen.getByLabelText("Password", { exact: true }),
    "Synthetic-test-password",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Create local account" }),
  );
  await screen.findByText("Workspace");
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});
