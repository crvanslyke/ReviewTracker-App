#!/usr/bin/env python3
"""Simple CLI app to track editorial and review work (SQLModel version)."""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select, text

# Database Configuration
# Use DATABASE_URL env var if available (Vercel/Production), else local SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///editorial_tracker.db")

DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


class WorkItem(SQLModel, table=True):
    __tablename__ = "work_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    reference_id: Optional[str] = None
    role: Optional[str] = None
    venue: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = "invited"
    decision: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


def get_engine():
    # check_same_thread=False is needed for SQLite when used with FastAPI/Uvicorn reloader
    connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
    return create_engine(DATABASE_URL, connect_args=connect_args)


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)


def now_timestamp() -> str:
    return datetime.now().strftime(DATETIME_FMT)


def add_item(
    session: Session,
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
    item = WorkItem(
        title=title,
        reference_id=reference_id,
        role=role,
        venue=venue,
        due_date=due_date,
        status=status,
        decision=decision,
        notes=notes,
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(item)
    session.commit()
    session.refresh(item)


def list_items(
    session: Session,
    status: str | None,
    sort_by: str = "due_date",
    sort_order: str = "ASC",
) -> Iterable[WorkItem]:
    statement = select(WorkItem)

    if status:
        statement = statement.where(WorkItem.status == status)

    # Dynamic sorting
    order_column = getattr(WorkItem, sort_by, WorkItem.due_date)
    
    if sort_order.upper() == "DESC":
        statement = statement.order_by(order_column.desc())
    else:
        statement = statement.order_by(order_column.asc())

    # Secondary sort by ID for stability
    statement = statement.order_by(WorkItem.id)

    return session.exec(statement).all()


def get_venues(session: Session) -> list[str]:
    statement = select(WorkItem.venue).where(WorkItem.venue != None).where(WorkItem.venue != "").distinct().order_by(WorkItem.venue)
    return session.exec(statement).all()


def update_item(session: Session, item_id: int, **fields: str | None) -> None:
    item = session.get(WorkItem, item_id)
    if not item:
        raise ValueError(f"Item with ID {item_id} not found.")

    updates_made = False
    for key, value in fields.items():
        if value is not None and hasattr(item, key):
            setattr(item, key, value)
            updates_made = True

    if updates_made:
        item.updated_at = now_timestamp()
        session.add(item)
        session.commit()
        session.refresh(item)


def export_csv(session: Session, output_path: Path) -> None:
    items = session.exec(select(WorkItem).order_by(WorkItem.due_date)).all()
    
    if not items:
        return

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        
        # Get headers from WorkItem fields
        headers = list(items[0].model_dump().keys())
        writer.writerow(headers)
        
        for item in items:
            writer.writerow([getattr(item, h) for h in headers])


def print_rows(items: Iterable[WorkItem]) -> None:
    items = list(items)
    if not items:
        print("No entries found.")
        return

    headers = items[0].model_dump().keys()
    # Basic columnar print - convert models to dicts for printing logic reuse
    rows = [item.model_dump() for item in items]
    
    columns = list(headers)
    widths = {column: len(column) for column in columns}
    
    for row in rows:
        for column in columns:
            val = str(row.get(column) or "")
            widths[column] = max(widths[column], len(val))

    header_str = " | ".join(column.ljust(widths[column]) for column in columns)
    divider = "-+-".join("-" * widths[column] for column in columns)
    
    print(header_str)
    print(divider)
    
    for row in rows:
        print(" | ".join(str(row.get(column) or "").ljust(widths[column]) for column in columns))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track editorial and peer-review work.",
    )
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
        choices=["due_date", "venue", "title", "reference_id"], # Matches model field names
        default="due_date",
        help="Sort results by field.",
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

    engine = get_engine()
    
    if args.command == "init":
        init_db(engine)
        print(f"Initialized database.")
        return

    # Auto-init for convenience
    init_db(engine)

    with Session(engine) as session:
        if args.command == "add":
            add_item(
                session,
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

        elif args.command == "list":
            # Map CLI arg 'due-date' to 'due_date' if needed, though we updated choices
            sort_field = args.sort.replace("-", "_") 
            rows = list_items(session, args.status, sort_by=sort_field)
            print_rows(rows)

        elif args.command == "update":
            update_item(
                session,
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

        elif args.command == "status":
            update_item(session, args.id, status=args.status)
            print("Status updated.")

        elif args.command == "export":
            export_csv(session, Path(args.output))
            print(f"Exported data to {args.output}.")


if __name__ == "__main__":
    main()
