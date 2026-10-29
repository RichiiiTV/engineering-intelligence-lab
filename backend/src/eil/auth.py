"""Local accounts, revocable opaque sessions and case ownership. No agent tools."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from pwdlib import PasswordHash

from .database import configure

COOKIE = "eil_session"
SESSION_SECONDS = 8 * 3600
IDLE_SECONDS = 30 * 60
_passwords = PasswordHash.recommended()
_dummy = _passwords.hash(secrets.token_urlsafe(32))
_login_slot = threading.BoundedSemaphore(2)


class AuthenticationError(ValueError):
    pass


class AuthenticationLimited(AuthenticationError):
    pass


@dataclass(frozen=True)
class Principal:
    id: str
    username: str
    role: str

    def public(self):
        return asdict(self)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def credentials(username, password):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", username):
        raise AuthenticationError(
            "Username must contain 3-40 letters, digits, dots, underscores or hyphens"
        )
    if not isinstance(password, str) or not 14 <= len(password) <= 128:
        raise AuthenticationError("Use a password of 14-128 characters")


def local_owner(directory):
    path = Path(directory) / "auth.sqlite3"
    if not path.is_file():
        return None
    with closing(sqlite3.connect(path)) as conn:
        row = conn.execute("SELECT value FROM auth_meta WHERE key='initial_owner'").fetchone()
        return row[0] if row else None


class AuthStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "auth.sqlite3"
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    created REAL NOT NULL, expires REAL NOT NULL, last_used REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS bootstrap (id INTEGER PRIMARY KEY CHECK(id=1), token_hash TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS failures (key TEXT PRIMARY KEY, count INTEGER NOT NULL, until REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_audit (id INTEGER PRIMARY KEY, at REAL, actor_id TEXT, kind TEXT, subject_id TEXT);
            """)
            from .audit import migrate

            migrate(conn)
            columns = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
            if "auth_version" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 0")
            columns = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
            if "auth_version" not in columns:
                conn.execute(
                    "ALTER TABLE sessions ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 0"
                )
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS audit_outbox(id TEXT PRIMARY KEY,at REAL,actor TEXT,kind TEXT,subject TEXT,details TEXT);
                CREATE TABLE IF NOT EXISTS audit_counters(kind TEXT PRIMARY KEY,count INTEGER NOT NULL,first REAL,last REAL);
            """)
        from .audit import migrate_history

        migrate_history(self.directory)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        configure(conn, "auth")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        from .audit import flush

        flush(self.directory)

    @staticmethod
    def audit(conn, actor, kind, subject=None, details=None):
        from .audit import enqueue

        enqueue(conn, actor, kind, subject, details)

    def users(self, *, offset=0, limit=50):
        with self.connection() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT id,username,role,active,(SELECT count(*) FROM sessions s WHERE s.user_id=users.id AND s.expires>? AND s.last_used>?) sessions FROM users ORDER BY username LIMIT ? OFFSET ?",
                    (time.time(), time.time() - IDLE_SECONDS, limit, offset),
                )
            ]

    def manage_user(self, actor, identity, *, role=None, active=None, revoke=False):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT role,active FROM users WHERE id=?", (actor.id,)
            ).fetchone()
            if not current or current["role"] != "admin" or not current["active"]:
                raise AuthenticationError("Administrator access is required")
            target = conn.execute("SELECT * FROM users WHERE id=?", (identity,)).fetchone()
            if not target:
                raise AuthenticationError("User not found")
            new_role = role if role is not None else target["role"]
            new_active = active if active is not None else bool(target["active"])
            if new_role not in {"member", "admin"}:
                raise AuthenticationError("Invalid role")
            if identity == actor.id and (new_role != "admin" or not new_active):
                raise AuthenticationError(
                    "You cannot disable or demote your own administrator account"
                )
            if (
                target["role"] == "admin"
                and target["active"]
                and (new_role != "admin" or not new_active)
            ):
                if (
                    conn.execute(
                        "SELECT count(*) FROM users WHERE role='admin' AND active=1"
                    ).fetchone()[0]
                    <= 1
                ):
                    raise AuthenticationError("At least one active administrator must remain")
            conn.execute(
                "UPDATE users SET role=?,active=? WHERE id=?", (new_role, int(new_active), identity)
            )
            if revoke or new_role != target["role"] or not new_active:
                conn.execute("UPDATE users SET auth_version=auth_version+1 WHERE id=?", (identity,))
                conn.execute("DELETE FROM sessions WHERE user_id=?", (identity,))
            self.audit(
                conn,
                actor.id,
                "sessions_revoked" if revoke else "user_updated",
                identity,
                {"old_role": target["role"], "role": new_role, "active": bool(new_active)},
            )
        return {
            "id": identity,
            "username": target["username"],
            "role": new_role,
            "active": bool(new_active),
        }

    def configured(self):
        with self.connection() as conn:
            return bool(conn.execute("SELECT 1 FROM users LIMIT 1").fetchone())

    def bootstrap(self):
        """Trusted operator CLI only; code never appears in an HTTP response or URL."""
        code = secrets.token_urlsafe(32)
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise AuthenticationError("Accounts are already configured; sign in instead")
            conn.execute(
                "INSERT OR REPLACE INTO bootstrap VALUES (1,?,?)", (digest(code), time.time() + 900)
            )
            self.audit(conn, "local-operator", "bootstrap_issued")
        return code

    def enroll(self, code, username, password):
        credentials(username, password)
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM bootstrap WHERE id=1").fetchone()
            if (
                conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                or not row
                or row["expires"] < time.time()
                or not hmac.compare_digest(row["token_hash"], digest(code))
            ):
                raise AuthenticationError("Invalid or expired setup code")
            user = Principal(str(uuid.uuid4()), username, "admin")
            hashed = _passwords.hash(password)
            conn.execute(
                "INSERT INTO users(id,username,password_hash,role) VALUES (?,?,?,?)",
                (user.id, username, hashed, user.role),
            )
            conn.execute("INSERT INTO auth_meta VALUES ('initial_owner',?)", (user.id,))
            conn.execute("DELETE FROM bootstrap")
            self.audit(conn, user.id, "account_enrolled", user.id)
        adopt_legacy(self.directory, user.id)
        return user

    def add_user(self, actor, username, password, role="member"):
        if actor.role != "admin" or role not in {"admin", "member"}:
            raise AuthenticationError("Administrator access is required")
        credentials(username, password)
        user = Principal(str(uuid.uuid4()), username, role)
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT role,active FROM users WHERE id=?", (actor.id,)
            ).fetchone()
            if not current or current["role"] != "admin" or not current["active"]:
                raise AuthenticationError("Administrator access is required")
            if conn.execute("SELECT count(*) FROM users").fetchone()[0] >= 1000:
                raise AuthenticationError("Workspace account limit reached (1000)")
            try:
                conn.execute(
                    "INSERT INTO users(id,username,password_hash,role) VALUES (?,?,?,?)",
                    (user.id, username, _passwords.hash(password), role),
                )
            except sqlite3.IntegrityError as exc:
                raise AuthenticationError("That username is unavailable") from exc
            self.audit(conn, actor.id, "account_created", user.id)
        return user

    def login(self, username, password, client="local"):
        if not _login_slot.acquire(blocking=False):
            raise AuthenticationLimited("Sign-in is busy. Try again shortly.")
        try:
            return self._login(username, password, client)
        finally:
            _login_slot.release()

    def _login(self, username, password, client):
        if len(username) > 40 or len(password) > 128:
            raise AuthenticationError("Invalid username or password")
        key = digest(username.casefold() + ":" + client)
        global_key = digest("client:" + client)
        current = time.time()
        with self.connection() as conn:
            for attempt_key, maximum in ((key, 5), (global_key, 20)):
                row = conn.execute("SELECT * FROM failures WHERE key=?", (attempt_key,)).fetchone()
                if row and row["until"] > current and row["count"] >= maximum:
                    raise AuthenticationLimited("Too many sign-in attempts. Wait five minutes.")
            user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        valid = _passwords.verify(password, user["password_hash"] if user else _dummy)
        if not valid or not user or not user["active"]:
            with self.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM failures WHERE until<?", (current,))
                for attempt_key in (key, global_key):
                    conn.execute(
                        "INSERT INTO failures VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",
                        (attempt_key, current + 300),
                    )
                self.audit(conn, None, "login_failed")
            raise AuthenticationError("Invalid username or password")
        token = secrets.token_urlsafe(32)
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            latest = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            if (
                not latest
                or not latest["active"]
                or latest["auth_version"] != user["auth_version"]
                or not hmac.compare_digest(latest["password_hash"], user["password_hash"])
            ):
                raise AuthenticationError("Credentials changed during sign-in. Try again.")
            conn.execute("DELETE FROM failures WHERE key=?", (key,))
            conn.execute(
                "DELETE FROM sessions WHERE expires<? OR last_used<?",
                (current, current - IDLE_SECONDS),
            )
            # A new legitimate sign-in retires the oldest of at most five sessions.
            conn.execute(
                "DELETE FROM sessions WHERE token_hash IN (SELECT token_hash FROM sessions WHERE user_id=? ORDER BY created DESC LIMIT -1 OFFSET 4)",
                (user["id"],),
            )
            conn.execute(
                "INSERT INTO sessions(token_hash,user_id,created,expires,last_used,auth_version) VALUES (?,?,?,?,?,?)",
                (
                    digest(token),
                    user["id"],
                    current,
                    current + SESSION_SECONDS,
                    current,
                    user["auth_version"],
                ),
            )
            self.audit(conn, user["id"], "login")
        return token, Principal(user["id"], user["username"], user["role"])

    def authenticate(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            raise AuthenticationError("Sign in to continue")
        with self.connection() as conn:
            row = conn.execute(
                "SELECT u.*,s.expires,s.last_used,s.auth_version session_version FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
                (digest(token),),
            ).fetchone()
            current = time.time()
            if (
                not row
                or not row["active"]
                or row["auth_version"] != row["session_version"]
                or row["expires"] <= current
                or row["last_used"] + IDLE_SECONDS <= current
            ):
                raise AuthenticationError("Session expired. Sign in again.")
            conn.execute(
                "UPDATE sessions SET last_used=? WHERE token_hash=?", (current, digest(token))
            )
            return Principal(row["id"], row["username"], row["role"])

    def logout(self, token):
        with self.connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM sessions WHERE token_hash=?", (digest(token or ""),)
            ).fetchone()
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (digest(token or ""),))
            if row:
                self.audit(conn, row[0], "logout")

    def change_password(self, actor, old, new):
        credentials(actor.username, new)
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT password_hash FROM users WHERE id=?", (actor.id,)).fetchone()
            if not row or not _passwords.verify(old, row[0]):
                raise AuthenticationError("Invalid current password")
            conn.execute(
                "UPDATE users SET password_hash=?,auth_version=auth_version+1 WHERE id=?",
                (_passwords.hash(new), actor.id),
            )
            conn.execute("DELETE FROM sessions WHERE user_id=?", (actor.id,))
            self.audit(conn, actor.id, "password_changed", actor.id)


def adopt_legacy(directory, owner):
    """Bind previously unowned local data to the first enrolled owner, never a later user."""
    from .evidence import EvidenceStore
    from .runs import RunStore

    evidence = EvidenceStore(directory)
    with evidence.connection() as conn:
        conn.execute("UPDATE cases SET owner_id=? WHERE owner_id IS NULL", (owner,))
    runs = RunStore(directory)
    with runs.connection() as conn:
        conn.execute(
            "UPDATE runs SET document=json_set(document,'$.owner_id',?) WHERE json_extract(document,'$.owner_id') IS NULL",
            (owner,),
        )
