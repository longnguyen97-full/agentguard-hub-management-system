#!/usr/bin/env python3
"""
AgentGuard Data Lifecycle & Disaster Recovery CLI.
Provides automated backup, restoration, and data purge for Dashboard & Langfuse.

Usage:
    python scripts/backup_manager.py stats
    python scripts/backup_manager.py backup [--target all|dashboard|langfuse] [--note "My backup"]
    python scripts/backup_manager.py list
    python scripts/backup_manager.py restore <backup_filename> [--target all|dashboard|langfuse]
    python scripts/backup_manager.py reset [--target all|dashboard|langfuse] [--yes]
"""

import argparse
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.backup import backup_manager


def cmd_stats(args):
    stats = backup_manager.get_storage_stats()
    print("=" * 60)
    print(" 📊 AGENTGUARD & LANGFUSE STORAGE ANALYTICS")
    print("=" * 60)
    d = stats["dashboard"]
    print(f"[*] Dashboard Database (SQLite): {d['db_path']}")
    print(f"    - Disk Size:      {d['size_formatted']} ({d['size_bytes']:,} bytes)")
    print(f"    - Total Runs:     {d['runs_count']:,}")
    print(f"    - Total Steps:    {d['steps_count']:,}")
    print(f"    - Memory Runs:    {d['memory_runs_count']:,}")
    print("-" * 60)
    lf = stats["langfuse"]
    conn_str = "CONNECTED" if lf["connected"] else "OFFLINE"
    print(f"[*] Langfuse Tracing Core: [{conn_str}] ({lf['host']})")
    print(f"    - Version:        {lf['version']}")
    print(f"    - ClickHouse Evs: {lf['clickhouse_events_count']:,}")
    print(f"    - Total Traces:   {lf['total_traces']:,}")
    print(f"    - Total Spans:    {lf['total_spans']:,}")
    print(f"    - Total Tokens:   {lf['total_tokens']:,}")
    print(f"    - Estimated Cost: ${lf['total_cost_usd']:.4f} (~{lf['total_cost_vnd']:,} VND)")
    print("-" * 60)
    bk = stats["backups_summary"]
    print(f"[*] Backups Directory:   {bk['directory']}")
    print(f"    - Total Archives: {bk['total_count']}")
    print(f"    - Total Size:     {bk['total_size_formatted']}")
    print("=" * 60)


def cmd_backup(args):
    print(f"[*] Creating backup archive (target: {args.target})...")
    res = backup_manager.create_backup(
        target=args.target,
        note=args.note or "Manual CLI Backup",
        include_langfuse=not args.no_langfuse
    )
    print(f"[+] Backup successfully created:")
    print(f"    - File: {res['filename']}")
    print(f"    - Path: {res['filepath']}")
    print(f"    - Size: {res['size_formatted']}")
    print(f"    - Date: {res['created_at']}")


def cmd_list(args):
    backups = backup_manager.list_backups()
    if not backups:
        print("[!] No backups found in backups/ directory.")
        return

    print("=" * 80)
    print(f" {'FILENAME':<36} | {'SIZE':<9} | {'RUNS':<6} | {'TARGET':<9} | {'NOTE'}")
    print("=" * 80)
    for b in backups:
        print(f" {b['filename']:<36} | {b['size_formatted']:<9} | {b['runs_count']:<6} | {b['target']:<9} | {b['note']}")
    print("=" * 80)
    print(f"Total: {len(backups)} backup archive(s).")


def cmd_restore(args):
    target_file = args.filename
    print(f"[!] Warning: Restoring from '{target_file}' will replace active operational state.")
    if not args.yes:
        confirm = input("Are you sure you want to proceed? [y/N]: ").strip().lower()
        if confirm not in ["y", "yes"]:
            print("[-] Restore aborted by user.")
            return

    res = backup_manager.restore_backup(target_file, target=args.target)
    print(f"[+] Backup restored successfully:")
    print(f"    - Restored Runs:     {res['restored_runs']}")
    print(f"    - Langfuse Restored: {res['restored_langfuse']}")
    print(f"    - Pre-restore Safety Backup: {res['pre_restore_backup']}")


def cmd_reset(args):
    print("=" * 60)
    print(" ⚠️  DANGER ZONE: DATA RESET & PURGE")
    print("=" * 60)
    print(f"Target to reset: {args.target.upper()}")
    print("This will PERMANENTLY ERASE runs, steps, and telemetry traces.")
    print("An automated pre-reset backup will be created before deletion.")

    if not args.yes:
        confirm = input("\nType 'RESET' to confirm permanent data deletion: ").strip()
        if confirm != "RESET":
            print("[-] Confirmation mismatch. Reset canceled.")
            return

    res = backup_manager.reset_data(
        target=args.target,
        preserve_langfuse_auth=not args.wipe_all_auth
    )
    print(f"[+] Data reset completed successfully:")
    print(f"    - Target:             {res['target']}")
    print(f"    - Dashboard Deleted:  {res['dashboard_deleted_runs']} runs")
    print(f"    - ClickHouse Cleared: {res['clickhouse_truncated']}")


def main():
    parser = argparse.ArgumentParser(description="AgentGuard Data Lifecycle CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # stats
    subparsers.add_parser("stats", help="Display storage analytics and health metrics")

    # backup
    p_backup = subparsers.add_parser("backup", help="Create a timestamped backup archive")
    p_backup.add_argument("--target", choices=["all", "dashboard", "langfuse"], default="all", help="Backup scope")
    p_backup.add_argument("--note", default="", help="Optional description note")
    p_backup.add_argument("--no-langfuse", action="store_true", help="Skip Langfuse Postgres/ClickHouse snapshot")

    # list
    subparsers.add_parser("list", help="List all available backup archives")

    # restore
    p_restore = subparsers.add_parser("restore", help="Restore state from a backup archive")
    p_restore.add_argument("filename", help="Backup filename or path")
    p_restore.add_argument("--target", choices=["all", "dashboard", "langfuse"], default="all", help="Restore scope")
    p_restore.add_argument("-y", "--yes", action="store_true", help="Bypass interactive prompt")

    # reset
    p_reset = subparsers.add_parser("reset", help="Purge operational data (sessions, steps, ClickHouse)")
    p_reset.add_argument("--target", choices=["all", "dashboard", "langfuse"], default="all", help="Reset scope")
    p_reset.add_argument("--wipe-all-auth", action="store_true", help="Also wipe Langfuse user accounts and projects")
    p_reset.add_argument("-y", "--yes", action="store_true", help="Bypass interactive confirmation")

    args = parser.parse_args()
    if args.command == "stats":
        cmd_stats(args)
    elif args.command == "backup":
        cmd_backup(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "restore":
        cmd_restore(args)
    elif args.command == "reset":
        cmd_reset(args)


if __name__ == "__main__":
    main()
