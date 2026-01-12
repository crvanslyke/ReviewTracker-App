#!/usr/bin/env python3
"""Simple CLI app to track editorial and review work."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

DB_FILENAME = "editorial_tracker.db"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def get_db_path(db_path: str | None) -> Path:
    return Path(db_path) if db_path else Path.cwd() / DB_FILENAME


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS work_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            reference_id TEXT,
            role TEXT,
            venue TEXT,
            due_date TEXT,
            status TEXT,
            decision TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


def now_timestamp() -> str:
    return datetime.now().strftime(DATETIME_FMT)


def add_item(
    connection: sqlite3.Connection,
    *,
    title: str,
    reference_id: str | None,
    role: str | None,
    venue: str | None,
    due_date: str | None,
    status: str | None,
    decision: str | None,
    notes: str | None,
) -> None:
    timestamp = now_timestamp()
    connection.execute(
        """
        INSERT INTO work_items (
            title, reference_id, role, venue, due_date, status, decision, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            reference_id,
            role,
            venue,
            due_date,
            status,
            decision,
            notes,
            timestamp,
            timestamp,
        ),
    )
    connection.commit()


def list_items(
    connection: sqlite3.Connection,
    status: str | None,
    sort_by: str = "due-date",
    sort_order: str = "ASC",
) -> Iterable[sqlite3.Row]:
    query = "SELECT * FROM work_items"
    params = []

    if status:
        query += " WHERE status = ?"
        params.append(status)

    order = "DESC" if sort_order.upper() == "DESC" else "ASC"

    # Whitelist allowed sort columns to prevent SQL injection
    allowed_sorts = {"title", "venue", "due_date", "reference_id", "status"}
    if sort_by not in allowed_sorts:
        sort_by = "due_date"

    # Specific handling for nulls if needed, otherwise generic sort
    if sort_by in ("venue", "due_date", "reference_id"):
        query += f" ORDER BY {sort_by} IS NULL, {sort_by} {order}"
    else:
        query += f" ORDER BY {sort_by} {order}"

    return connection.execute(query, params)


def get_venues(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT DISTINCT venue FROM work_items WHERE venue IS NOT NULL AND venue != '' ORDER BY venue"
    ).fetchall()
    return [row["venue"] for row in rows]


def update_item(connection: sqlite3.Connection, item_id: int, **fields: str | None) -> None:
    updates = {key: value for key, value in fields.items() if value is not None}
    if not updates:
        raise ValueError("No fields provided to update.")

    updates["updated_at"] = now_timestamp()
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values())
    values.append(item_id)

    connection.execute(f"UPDATE work_items SET {set_clause} WHERE id = ?", values)
    connection.commit()


def export_csv(connection: sqlite3.Connection, output_path: Path) -> None:
    rows = connection.execute("SELECT * FROM work_items ORDER BY due_date IS NULL, due_date").fetchall()
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(rows[0].keys() if rows else [
            "id",
            "title",
            "reference_id",
            "role",
            "venue",
            "due_date",
            "status",
            "decision",
            "notes",
            "created_at",
            "updated_at",
        ])
        for row in rows:
            writer.writerow(row)


def print_rows(rows: Iterable[sqlite3.Row]) -> None:
    rows = list(rows)
    if not rows:
        print("No entries found.")
        return

    columns = rows[0].keys()
    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(str(row[column] or "")))

    header = " | ".join(column.ljust(widths[column]) for column in columns)
    divider = "-+-".join("-" * widths[column] for column in columns)
    print(header)
    print(divider)
    for row in rows:
        print(" | ".join(str(row[column] or "").ljust(widths[column]) for column in columns))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track editorial and peer-review work.",
    )
    parser.add_argument("--db", help="Path to the SQLite database file.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize the database.")

    add_parser = subparsers.add_parser("add", help="Add a new work item.")
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--reference-id", help="Manuscript, paper, or submission ID.")
    add_parser.add_argument("--role", help="Reviewer, Associate Editor, Senior Editor, etc.")
    add_parser.add_argument("--venue", help="Journal or conference name.")
    add_parser.add_argument("--due-date", help="Due date (YYYY-MM-DD).")
    add_parser.add_argument("--status", help="Status (invited, in_review, completed, etc.).")
    add_parser.add_argument("--decision", help="Decision or outcome.")
    add_parser.add_argument("--notes", help="Additional notes.")

    list_parser = subparsers.add_parser("list", help="List tracked work items.")
    list_parser.add_argument("--status", help="Filter by status.")
    list_parser.add_argument(
        "--sort",
        choices=["due-date", "venue"],
        default="due-date",
        help="Sort results by due date or venue.",
    )

    update_parser = subparsers.add_parser("update", help="Update a work item.")
    update_parser.add_argument("id", type=int)
    update_parser.add_argument("--title")
    update_parser.add_argument("--reference-id")
    update_parser.add_argument("--role")
    update_parser.add_argument("--venue")
    update_parser.add_argument("--due-date")
    update_parser.add_argument("--status")
    update_parser.add_argument("--decision")
    update_parser.add_argument("--notes")

    status_parser = subparsers.add_parser("status", help="Update only the status of an item.")
    status_parser.add_argument("id", type=int)
    status_parser.add_argument("--status", required=True)

    export_parser = subparsers.add_parser("export", help="Export to CSV.")
    export_parser.add_argument("output", help="Output CSV path.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    db_path = get_db_path(args.db)
    connection = connect(db_path)

    if args.command == "init":
        init_db(connection)
        print(f"Initialized database at {db_path}")
        return

    init_db(connection)

    if args.command == "add":
        add_item(
            connection,
            title=args.title,
            reference_id=args.reference_id,
            role=args.role,
            venue=args.venue,
            due_date=args.due_date,
            status=args.status,
            decision=args.decision,
            notes=args.notes,
        )
        print("Work item added.")
        return

    if args.command == "list":
        rows = list_items(connection, args.status, sort_by=args.sort)
        print_rows(rows)
        return

    if args.command == "update":
        update_item(
            connection,
            args.id,
            title=args.title,
            reference_id=args.reference_id,
            role=args.role,
            venue=args.venue,
            due_date=args.due_date,
            status=args.status,
            decision=args.decision,
            notes=args.notes,
        )
        print("Work item updated.")
        return

    if args.command == "status":
        update_item(connection, args.id, status=args.status)
        print("Status updated.")
        return

    if args.command == "export":
        export_csv(connection, Path(args.output))
        print(f"Exported data to {args.output}.")
        return


if __name__ == "__main__":
    main()
