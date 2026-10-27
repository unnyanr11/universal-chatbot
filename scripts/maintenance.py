"""PostgreSQL Compose backup, restore and guarded updates. Requires an existing setup."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from setup import ROOT, SetupError, read_config, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--output", required=True)
    verify = sub.add_parser("verify-backup")
    verify.add_argument("--input", required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--input", required=True)
    restore.add_argument("--database", default="assistant")
    restore.add_argument("--confirm-empty-database", action="store_true")
    upgrade = sub.add_parser("upgrade")
    upgrade.add_argument("--backup", required=True)
    args = parser.parse_args()
    values = read_config(ROOT / ".env")
    if not values.get("POSTGRES_PASSWORD"):
        raise SetupError("Run setup first or restore the original private .env configuration.")
    env = {**os.environ, **values}
    compose = ["docker", "compose", "--env-file", str(ROOT / ".env"), "-f", "compose.yaml"]
    if values.get("APP_DOMAIN"):
        compose += ["-f", "compose.public.yaml"]

    def execute(parts, **kwargs):
        return run(compose + parts, env=env, **kwargs)

    def make_backup(path):
        path = Path(path).resolve()
        if path.is_relative_to(ROOT):
            raise SetupError("Store backups outside the source checkout.")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as output:
                subprocess.run(
                    compose
                    + [
                        "exec",
                        "-T",
                        "db",
                        "pg_dump",
                        "-U",
                        "assistant",
                        "-d",
                        "assistant",
                        "--format=custom",
                    ],
                    cwd=ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    check=True,
                )
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        print("Database backup saved to", path)
        print("Back up .env separately to retain database and provider encryption/signing secrets.")

    if args.action == "backup":
        make_backup(args.output)
    elif args.action == "verify-backup":
        with open(args.input, "rb") as source:
            subprocess.run(
                compose + ["exec", "-T", "db", "pg_restore", "--list"],
                cwd=ROOT,
                env=env,
                stdin=source,
                stdout=subprocess.DEVNULL,
                check=True,
            )
        print(
            "Archive table of contents is readable. Test a restore into a separate empty database."
        )
    elif args.action == "restore":
        if not args.confirm_empty_database or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]{0,62}", args.database
        ):
            raise SetupError("Restore requires --confirm-empty-database and a safe database name.")
        execute(["up", "-d", "db"])
        count = execute(
            [
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "assistant",
                "-d",
                args.database,
                "-Atc",
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'",
            ],
            capture=True,
        ).strip()
        if count != "0":
            raise SetupError(
                "Target database must be empty. Restore to a fresh database; no existing data is overwritten."
            )
        execute(["stop", "api", "worker"])
        with open(args.input, "rb") as source:
            subprocess.run(
                compose
                + [
                    "exec",
                    "-T",
                    "db",
                    "pg_restore",
                    "--no-owner",
                    "--no-acl",
                    "--single-transaction",
                    "--exit-on-error",
                    "-U",
                    "assistant",
                    "-d",
                    args.database,
                ],
                cwd=ROOT,
                env=env,
                stdin=source,
                check=True,
            )
        print(
            "Restore complete. Run setup with the restored original .env before serving requests."
        )
    else:
        if run(["git", "status", "--porcelain"], capture=True).strip():
            raise SetupError("Commit or move local source changes before upgrading.")
        previous = run(["git", "rev-parse", "HEAD"], capture=True).strip()
        make_backup(args.backup)
        print("Previous source commit:", previous)
        run(["git", "pull", "--ff-only"])
        execute(["stop", "api", "worker"])
        run([sys.executable, "scripts/setup.py", "--no-browser"], env=env)
        print(
            "Upgrade checks passed. Preserve the backup and previous source commit until acceptance."
        )


if __name__ == "__main__":
    try:
        main()
    except (SetupError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("Maintenance stopped:", exc, file=sys.stderr)
        sys.exit(1)
