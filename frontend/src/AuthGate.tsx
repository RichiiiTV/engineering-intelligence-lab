import {
  createContext,
  useContext,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { api, post } from "./api";
import StorageSettings from "./StorageSettings";
import AdminWorkspace from "./AdminWorkspace";
import "./user.css";

type User = { id: string; username: string; role: string };
const UserContext = createContext<User | null>(null);
export const useCurrentUser = () => useContext(UserContext);

export default function AuthGate({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [account, setAccount] = useState(false);
  const [administration, setAdministration] = useState(false);
  useEffect(() => {
    let live = true;
    void api<{ configured: boolean }>("/api/auth/status")
      .then(async (status) => {
        if (!live) return;
        setConfigured(status.configured);
        if (status.configured) {
          try {
            const result = await api<{ user: User }>("/api/auth/me");
            if (live) setUser(result.user);
          } catch {
            /* Show the sign-in form. */
          }
        }
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    const expired = () => {
      setUser(null);
      setPassword("");
      setAccount(false);
      setAdministration(false);
    };
    window.addEventListener("eil-auth-expired", expired);
    return () => {
      live = false;
      window.removeEventListener("eil-auth-expired", expired);
    };
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await post<{ user: User }>(
        configured ? "/api/auth/login" : "/api/auth/enroll",
        { username, password, ...(!configured ? { code } : {}) },
      );
      setUser(result.user);
      setConfigured(true);
      setPassword("");
      setCode("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    try {
      await post("/api/auth/logout");
    } catch (e) {
      setError(String(e));
      return;
    }
    setUser(null);
    setPassword("");
    setAccount(false);
    setAdministration(false);
  }
  if (!user)
    return (
      <div className="user-app">
        <main className="ux-main auth-main">
          <h1>
            {configured === false
              ? "Lokales Konto einrichten"
              : "Im Arbeitsbereich anmelden"}
          </h1>
          {configured === null && !error ? (
            <p>Arbeitsbereich wird geöffnet…</p>
          ) : (
            <form className="siemens-form" onSubmit={(e) => void submit(e)}>
              {configured === false && (
                <>
                  <p>
                    Führe diesen Befehl im Projektordner aus, um einen
                    Einrichtungscode zu erhalten:
                  </p>
                  <code>uv run python -m eil.cli auth-bootstrap</code>
                  <label htmlFor="auth-code">Einmaliger Einrichtungscode</label>
                  <input
                    id="auth-code"
                    autoComplete="off"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    required
                    maxLength={128}
                  />
                  <p>
                    Der Code läuft nach 15 Minuten ab. Bestehende lokale Fälle
                    werden diesem ersten Konto zugeordnet.
                  </p>
                </>
              )}
              <label htmlFor="auth-user">Benutzername</label>
              <input
                id="auth-user"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
                maxLength={40}
              />
              <label htmlFor="auth-password">Passwort</label>
              <input
                id="auth-password"
                type="password"
                autoComplete={configured ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={configured ? 1 : 14}
                maxLength={128}
              />
              {error && (
                <p className="ux-error" role="alert">
                  {error}
                </p>
              )}
              <button className="ux-primary" disabled={busy} type="submit">
                {busy
                  ? "Bitte warten…"
                  : configured
                    ? "Anmelden"
                    : "Lokales Konto erstellen"}
              </button>
            </form>
          )}
          {configured === null && error && <p role="alert">{error}</p>}
        </main>
      </div>
    );
  return (
    <UserContext.Provider value={user}>
      <aside className="auth-strip">
        <span>Angemeldet als {user.username}</span>
        <button onClick={() => setAccount(!account)}>Konto</button>
        {user.role === "admin" && (
          <button
            onClick={() => {
              setAdministration(!administration);
              setAccount(false);
            }}
          >
            Administration
          </button>
        )}
        <button onClick={() => void logout()}>Abmelden</button>
        {error && <span role="alert">{error}</span>}
      </aside>
      {account && (
        <Account
          user={user}
          onChanged={() => {
            setUser(null);
            setAccount(false);
          }}
        />
      )}
      {account && user.role === "admin" && (
        <section className="account-panel">
          <StorageSettings admin={user.role === "admin"} />
        </section>
      )}
      {administration && user.role === "admin" ? (
        <AdminWorkspace
          currentUserId={user.id}
          onClose={() => setAdministration(false)}
        />
      ) : (
        children
      )}
    </UserContext.Provider>
  );
}

function Account({ user, onChanged }: { user: User; onChanged: () => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState("");
  async function password(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await post("/api/auth/password", {
        current_password: current,
        new_password: next,
      });
      setCurrent("");
      setNext("");
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  return (
    <section className="account-panel" aria-label="Kontoeinstellungen">
      <h2>Kontoeinstellungen</h2>
      <form className="siemens-form" onSubmit={(e) => void password(e)}>
        <h3>Passwort ändern</h3>
        <label htmlFor="old-password">Aktuelles Passwort</label>
        <input
          id="old-password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
          maxLength={128}
        />
        <label htmlFor="new-password">Neues Passwort</label>
        <input
          id="new-password"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
          minLength={14}
          maxLength={128}
        />
        <button className="ux-secondary">
          Passwort aktualisieren und alle Sitzungen abmelden
        </button>
      </form>
      {user.role === "admin" && (
        <p>Benutzer unter Administration / Benutzer verwalten.</p>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
