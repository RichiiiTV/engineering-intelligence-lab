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
        return new Response(JSON.stringify({ detail: "Anmelden" }), {
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
  await screen.findByRole("button", { name: "Anmelden" });
  expect(screen.queryByText("Private workspace data")).toBeNull();
  await userEvent.type(screen.getByLabelText("Benutzername"), "owner");
  await userEvent.type(
    screen.getByLabelText("Passwort", { exact: true }),
    "Synthetic-test-password",
  );
  await userEvent.click(screen.getByRole("button", { name: "Anmelden" }));
  await screen.findByText("Private workspace data");
  await userEvent.click(screen.getByRole("button", { name: "Abmelden" }));
  await screen.findByRole("button", { name: "Anmelden" });
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
      <p>Arbeitsbereich</p>
    </AuthGate>,
  );
  await screen.findByLabelText("Einmaliger Einrichtungscode");
  await userEvent.type(
    screen.getByLabelText("Einmaliger Einrichtungscode"),
    "one-time-code",
  );
  await userEvent.type(screen.getByLabelText("Benutzername"), "owner");
  await userEvent.type(
    screen.getByLabelText("Passwort", { exact: true }),
    "Synthetic-test-password",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Lokales Konto erstellen" }),
  );
  await screen.findByText("Arbeitsbereich");
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});
