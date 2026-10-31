import { t } from "./i18n";
import { requestError } from "./locale";
import { getLanguage } from "./i18n";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    headers.set("X-EIL-Language", getLanguage());
    response = await fetch(path, { ...init, headers });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new Error(
      t(
        "Keine Verbindung zum lokalen Dienst. Bitte Verbindung prüfen und erneut versuchen.",
      ),
    );
  }
  if (!response.ok) {
    if (
      response.status === 401 &&
      (!path.startsWith("/api/auth/") ||
        path === "/api/auth/me" ||
        path.startsWith("/api/auth/users"))
    )
      window.dispatchEvent(new Event("eil-auth-expired"));
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    } catch {
      /* Keep the HTTP error if the server did not return JSON. */
    }
    throw new Error(requestError(detail, response.status));
  }
  return response.json() as Promise<T>;
}
export function post<T>(path: string, body?: unknown): Promise<T> {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}
export function download(
  name: string,
  content: string,
  type = "application/json",
) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
