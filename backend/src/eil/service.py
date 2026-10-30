"""Single-owner SQLite queue with a killable Windows-spawn worker process."""

from __future__ import annotations

import multiprocessing
import os
import sqlite3
import threading
import time
from pathlib import Path

from .runs import STOPPED, RunConflict, RunStore
from .settings import STATE_DIR


def exclusive_owner(path, timeout=0):
    conn = sqlite3.connect(path, timeout=timeout, check_same_thread=False)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS owner (id INTEGER)")
        conn.execute("BEGIN EXCLUSIVE")
    except sqlite3.OperationalError as exc:
        conn.close()
        raise RunConflict(
            "This state directory already has an active service; use its API"
        ) from exc
    return conn


def worker_main(directory, run_id):
    from .execution import execute_run

    # A hard-crashed API must not leave an orphan model client alive indefinitely.
    parent = multiprocessing.parent_process()
    if parent is not None:

        def watch_parent():
            while parent.is_alive():
                time.sleep(0.1)
            os._exit(75)

        threading.Thread(target=watch_parent, daemon=True).start()
    owner = exclusive_owner(Path(directory) / "worker-owner.sqlite3", timeout=5)
    try:
        execute_run(directory, run_id)
    finally:
        owner.close()


class RunService:
    """One active investigation and at most twenty waiting jobs, for local development."""

    def __init__(self, directory=STATE_DIR, *, worker_target=worker_main):
        if (Path(directory) / ".restore-incomplete").exists():
            raise RunConflict(
                "This restore is incomplete; verify/restore a backup into a fresh directory"
            )
        self.store = RunStore(directory)
        self.worker_target = worker_target
        self._stop = threading.Event()
        self._thread = None
        self._owner = None
        self._fatal_error = None
        self._active_id = None

    def start(self):
        if self._thread is not None:
            raise RunConflict("Service has already started")
        self._owner = exclusive_owner(self.store.directory / "service-owner.sqlite3")
        try:
            self.store.recover()
            self._thread = threading.Thread(
                target=self._loop, name="eil-run-supervisor", daemon=True
            )
            self._thread.start()
        except BaseException:
            self._owner.close()
            self._owner = None
            raise
        return self

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                raise RuntimeError("Run supervisor did not stop")
        if self._owner is not None:
            self._owner.close()
            self._owner = None

    def submit(
        self,
        question,
        limits=None,
        *,
        case_id=None,
        use_mock_mcp=False,
        owner_id=None,
        siemens=None,
        chat_mode=False,
        use_library=False,
        library_document_ids=None,
        machine_id=None,
        machine_document_ids=None,
    ):
        if self._stop.is_set() or self._fatal_error is not None:
            raise RunConflict("Run service is unavailable; restart the API")
        return self.store.create(
            question,
            limits,
            case_id=case_id,
            use_mock_mcp=use_mock_mcp,
            owner_id=owner_id,
            siemens=siemens,
            chat_mode=chat_mode,
            use_library=use_library,
            library_document_ids=library_document_ids,
            machine_id=machine_id,
            machine_document_ids=machine_document_ids,
        )

    def wait(self, run_id, timeout=610):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self.store.get(run_id)
            if run["status"] in STOPPED and self._active_id != run_id:
                return run
            if self._fatal_error is not None:
                raise RunConflict("Run supervisor stopped; restart the API to recover")
            time.sleep(0.05)
        raise TimeoutError("Timed out waiting for investigation status")

    def _loop(self):
        try:
            while not self._stop.is_set():
                run = self.store.claim()
                if run is None:
                    self._stop.wait(0.05)
                    continue
                self._active_id = run["id"]
                try:
                    self._supervise(run)
                finally:
                    self._active_id = None
        except Exception as exc:
            # Retain exclusive ownership until close; never silently start a second dispatcher.
            self._fatal_error = type(exc).__name__

    def _supervise(self, run):
        process = multiprocessing.get_context("spawn").Process(
            target=self.worker_target, args=(str(self.store.directory), run["id"]), daemon=True
        )
        started = time.monotonic()
        final_status = None
        try:
            process.start()
            self.store.change(run["id"], lambda r, c: r.update(worker_pid=process.pid))
            while process.is_alive():
                current = self.store.get(run["id"])
                elapsed = run["elapsed_seconds"] + time.monotonic() - started
                if current["control"]:
                    final_status = "paused" if current["control"] == "pause" else "cancelled"
                elif self._stop.is_set():
                    final_status = "interrupted"
                elif elapsed >= run["limits"]["timeout_seconds"]:
                    final_status = "timed_out"
                if final_status:
                    process.terminate()
                    break
                self.store.change(run["id"], lambda r, c: r.update(elapsed_seconds=elapsed))
                self._stop.wait(0.05)
            process.join(timeout=3)
            if process.is_alive():
                process.kill()
                process.join(timeout=3)
            elapsed = run["elapsed_seconds"] + time.monotonic() - started
            current = self.store.change(
                run["id"], lambda r, c: r.update(elapsed_seconds=elapsed, worker_pid=None)
            )
            if current["status"] == "running":
                if current["control"]:
                    final_status = "paused" if current["control"] == "pause" else "cancelled"
                status = final_status or "interrupted"
                error = None
                if status == "timed_out":
                    error = {"code": "time_budget", "message": "Total run time budget exhausted"}
                elif status == "interrupted":
                    error = {
                        "code": "worker_interrupted",
                        "message": "Worker interrupted. Resume from the latest durable checkpoint.",
                        "exit_code": process.exitcode,
                    }
                self.store.finish(run["id"], status, error=error, force=True)
        except Exception as exc:
            self.store.finish(
                run["id"],
                "failed",
                force=True,
                error={
                    "code": "worker_error",
                    "message": f"Worker could not run ({type(exc).__name__}). Check local resources and resume.",
                },
            )
        finally:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=3)
                process.close()
