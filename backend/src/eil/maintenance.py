"""Trusted local operator commands; restoration never overwrites a state directory."""

import argparse
import json
import zipfile
from pathlib import Path

from .auth import AuthStore, Principal, local_owner
from .database import StorageFull
from .runs import RunConflict
from .service import exclusive_owner
from .settings import STATE_DIR
from .storage import StorageManager, restore_backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("status", "backup", "restore", "retention-plan", "retention-apply")
    )
    parser.add_argument("--state-dir", type=Path, default=STATE_DIR)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--plan-id")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--confirmation")
    args = parser.parse_args(argv)
    try:
        if args.command == "restore":
            if not args.archive or not args.destination:
                parser.error("Restore requires --archive and --destination (a NEW directory)")
            result = restore_backup(args.archive, args.destination)
        else:
            manager = StorageManager(args.state_dir)
            # An operator CLI must not race the live service. Its API provides
            # coordinated backup/retention while the service is running.
            owner = exclusive_owner(manager.directory / "service-owner.sqlite3")
            try:
                actor_id = local_owner(manager.directory)
                with AuthStore(manager.directory).connection() as conn:
                    row = conn.execute(
                        "SELECT id,username,role FROM users WHERE id=?", (actor_id,)
                    ).fetchone()
                actor = (
                    Principal(row[0], row[1], row[2])
                    if row
                    else Principal("local-operator", "local-operator", "admin")
                )
                if args.command == "status":
                    result = manager.status()
                elif args.command == "backup":
                    result = manager.create_backup(actor)
                elif args.command == "retention-plan":
                    result = manager.retention_plan(actor)
                else:
                    if not args.plan_id or not args.expected_sha256 or not args.confirmation:
                        parser.error(
                            "Apply requires the reviewed --plan-id, --expected-sha256 and --confirmation"
                        )
                    result = manager.apply_retention(
                        args.plan_id, args.expected_sha256, actor, args.confirmation
                    )
            finally:
                owner.close()
    except (RunConflict, StorageFull, ValueError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Maintenance stopped: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
