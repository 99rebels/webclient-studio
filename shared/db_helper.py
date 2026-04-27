"""Database helper for Freelance Forge.

The only module that touches SQLite. All sub-skills go through this.

Cross-cutting rules (enforced by the wrappers, not by the caller):
- Every write to `leads` / `tasks` also writes an `activity_log` row in the same transaction.
- `update_lead_status` auto-updates `status_since` and `date_updated`.
- `record_follow_up` updates `last_follow_up` only — never `status_since`.
- Fuzzy match = case-insensitive `LIKE %query%`. On >1 match, return all candidates.

Run as a module to get the CLI shim:
    python -m db_helper <command> [args...]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_DIR_NAME = ".freelance-forge"


def get_config_dir() -> Path:
    """Resolve the config directory.

    Honours $FREELANCE_FORGE_CONFIG_DIR; otherwise ~/.freelance-forge/.
    Creates the directory tree on first call.
    """
    env = os.environ.get("FREELANCE_FORGE_CONFIG_DIR")
    base = Path(env).expanduser() if env else Path.home() / DEFAULT_CONFIG_DIR_NAME
    for sub in ("reports/qualifications", "reports/proposals", "reports/projects", "exports"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def get_shared_dir() -> Path:
    """Resolve the shared scripts directory.

    Order: env var > ~/.freelance-forge/shared/ > this module's parent (dev).
    """
    env = os.environ.get("FREELANCE_FORGE_SHARED_DIR")
    if env:
        return Path(env).expanduser()
    # Standard install: shared scripts live alongside the config
    config_dir = get_config_dir()
    shared = config_dir / "shared"
    if shared.is_dir():
        return shared
    # Dev fallback: this module is in the source repo's shared/ folder
    return Path(__file__).resolve().parent


def db_path() -> Path:
    return get_config_dir() / "pipeline.db"


def config_path() -> Path:
    return get_config_dir() / "config.json"


# ---------------------------------------------------------------------------
# Time + IDs
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Schema (storage.md §3)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS leads (
        id              TEXT PRIMARY KEY,
        company         TEXT NOT NULL,
        website         TEXT,
        contact_name    TEXT,
        contact_email   TEXT,
        status          TEXT NOT NULL DEFAULT 'lead',
        lead_score      INTEGER,
        data_confidence TEXT,
        date_added      TEXT NOT NULL,
        date_updated    TEXT NOT NULL,
        proposal_date   TEXT,
        last_follow_up  TEXT,
        status_since    TEXT NOT NULL,
        next_action     TEXT,
        research_notes  TEXT,
        pitch_notes     TEXT,
        discovery_notes TEXT,
        proposal_summary TEXT,
        project_path    TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)",
    "CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(lead_score)",
    "CREATE INDEX IF NOT EXISTS idx_leads_proposal_date ON leads(proposal_date)",
    "CREATE INDEX IF NOT EXISTS idx_leads_company ON leads(company)",
    "CREATE INDEX IF NOT EXISTS idx_leads_status_since ON leads(status_since)",
    """
    CREATE TABLE IF NOT EXISTS tags (
        id          TEXT PRIMARY KEY,
        name        TEXT UNIQUE NOT NULL,
        category    TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lead_tags (
        lead_id     TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
        tag_id      TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (lead_id, tag_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS activity_log (
        id          TEXT PRIMARY KEY,
        lead_id     TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
        action      TEXT NOT NULL,
        details     TEXT,
        created_at  TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_activity_lead ON activity_log(lead_id)",
    "CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at)",
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id              TEXT PRIMARY KEY,
        lead_id         TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
        task_name       TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'todo',
        priority        TEXT DEFAULT 'medium',
        due_date        TEXT,
        notes           TEXT,
        is_deliverable  INTEGER DEFAULT 0,
        date_created    TEXT NOT NULL,
        date_updated    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tasks_lead ON tasks(lead_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)",
]

_SCHEMA_READY = False


def _ensure_schema(conn: sqlite3.Connection) -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    for stmt in _SCHEMA_SQL:
        conn.execute(stmt)
    # Migration: rename research_quality → data_confidence (2026-04-27)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(leads)").fetchall()}
    if "research_quality" in cols and "data_confidence" not in cols:
        conn.execute("ALTER TABLE leads RENAME COLUMN research_quality TO data_confidence")
    # Migration: add pitch_notes column (2026-04-27)
    if "pitch_notes" not in cols:
        conn.execute("ALTER TABLE leads ADD COLUMN pitch_notes TEXT")
    _SCHEMA_READY = True


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a connection, ensure schema, run inside a transaction."""
    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        _ensure_schema(conn)
        conn.execute("BEGIN")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Config (storage.md §4)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "preferences": {
        "currency": null,
        "followUpDays": 5,
        "statusFollowUpDays": {
            "lead": 5,
            "qualified": 7,
            "proposal_sent": 5,
            "onboarding": 10,
            "active": None,
            "complete": None,
            "lost": None,
        },
        "defaultStatuses": [
            "lead", "qualified", "proposal_sent", "onboarding",
            "active", "complete", "lost",
        ],
        "defaultPriorities": ["high", "medium", "low"],
        "defaultTaskStatuses": ["todo", "in_progress", "done"],
        "pricingStrategy": None,
    }
}


def get_config() -> dict[str, Any]:
    p = config_path()
    if not p.exists():
        p.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        return json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    return json.loads(p.read_text())


def update_config(path: list[str], value: Any) -> dict[str, Any]:
    """Update a nested key. e.g. update_config(['preferences', 'pricingStrategy'], 'day_rate')."""
    cfg = get_config()
    cursor = cfg
    for key in path[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[path[-1]] = value
    config_path().write_text(json.dumps(cfg, indent=2))
    return cfg


# ---------------------------------------------------------------------------
# Activity log (private; called from every write)
# ---------------------------------------------------------------------------

def _log(conn: sqlite3.Connection, lead_id: str, action: str, details: str | None = None) -> None:
    conn.execute(
        "INSERT INTO activity_log (id, lead_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (_new_id(), lead_id, action, details, _now()),
    )


def log_activity(lead_id: str, action: str, details: str | None = None) -> None:
    """Public helper for free-form activity logs (e.g. user-reported notes).

    Internal CRUD writes log automatically — only use this for entries that
    don't have a corresponding write (e.g. manual `note_added`).
    """
    with get_connection() as conn:
        _log(conn, lead_id, action, details)


def get_lead_activity(lead_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM activity_log WHERE lead_id = ? ORDER BY created_at ASC",
            (lead_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_activity(days: int = 7) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT a.*, l.company FROM activity_log a "
            "JOIN leads l ON l.id = a.lead_id "
            "WHERE a.created_at >= datetime('now', ?) "
            "ORDER BY a.created_at DESC",
            (f"-{int(days)} days",),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Leads — CRUD
# ---------------------------------------------------------------------------

_LEAD_FIELDS = (
    "company", "website", "contact_name", "contact_email", "status",
    "lead_score", "data_confidence", "proposal_date", "last_follow_up",
    "next_action", "research_notes", "pitch_notes", "discovery_notes", "proposal_summary",
    "project_path",
)


def add_lead(
    company: str,
    *,
    website: str | None = None,
    contact_name: str | None = None,
    contact_email: str | None = None,
    lead_score: int | None = None,
    data_confidence: str | None = None,
    research_notes: str | None = None,
    pitch_notes: str | None = None,
    status: str = "lead",
    suggested_tags: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Insert a new lead. Logs `lead_created` (and `lead_scored` if score given).

    Suggested tags are inserted in the same transaction.
    """
    now = _now()
    lead_id = _new_id()
    row = {
        "id": lead_id,
        "company": company,
        "website": website,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "status": status,
        "lead_score": lead_score,
        "data_confidence": data_confidence,
        "date_added": now,
        "date_updated": now,
        "status_since": now,
        "research_notes": research_notes,
        "pitch_notes": pitch_notes,
    }
    if dry_run:
        return {"would_insert": row, "would_tag": suggested_tags or []}

    with get_connection() as conn:
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" * len(row))
        conn.execute(f"INSERT INTO leads ({cols}) VALUES ({placeholders})", tuple(row.values()))
        _log(conn, lead_id, "lead_created", f"Created lead for {company}")
        if lead_score is not None:
            _log(conn, lead_id, "lead_scored", f"Score: {lead_score}")
        for tag in suggested_tags or []:
            _add_tag_in_conn(conn, lead_id, tag, category="custom")
    return get_lead_by_id(lead_id) or row


def get_lead_by_id(lead_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(row) if row else None


def get_lead_by_company(name: str) -> list[dict[str, Any]]:
    """Fuzzy match: case-insensitive LIKE %name%. Returns all candidates."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM leads WHERE company LIKE ? COLLATE NOCASE ORDER BY date_added DESC",
            (f"%{name}%",),
        ).fetchall()
    return [dict(r) for r in rows]


def search_leads(query: str) -> list[dict[str, Any]]:
    """Search company / contact_name / contact_email / research_notes."""
    pat = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM leads WHERE "
            "company LIKE ? COLLATE NOCASE OR "
            "contact_name LIKE ? COLLATE NOCASE OR "
            "contact_email LIKE ? COLLATE NOCASE OR "
            "research_notes LIKE ? COLLATE NOCASE "
            "ORDER BY date_added DESC",
            (pat, pat, pat, pat),
        ).fetchall()
    return [dict(r) for r in rows]


def get_leads_by_status(status: str | None = None) -> dict[str, list[dict[str, Any]]] | list[dict[str, Any]]:
    """If status is None, return dict grouped by status. Else return list for that status."""
    with get_connection() as conn:
        if status is None:
            rows = conn.execute(
                "SELECT * FROM leads ORDER BY status, COALESCE(lead_score, 0) DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leads WHERE status = ? ORDER BY COALESCE(lead_score, 0) DESC",
                (status,),
            ).fetchall()
    if status is not None:
        return [dict(r) for r in rows]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(r["status"], []).append(dict(r))
    return grouped


def get_leads_sorted_by_score() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY COALESCE(lead_score, 0) DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_lead_status(lead_id: str, new_status: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Update status; auto-updates status_since and date_updated; logs status_changed."""
    if dry_run:
        return {"would_update": {"id": lead_id, "status": new_status}}
    now = _now()
    with get_connection() as conn:
        old = conn.execute("SELECT status FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not old:
            raise ValueError(f"Lead {lead_id} not found")
        conn.execute(
            "UPDATE leads SET status = ?, status_since = ?, date_updated = ? WHERE id = ?",
            (new_status, now, now, lead_id),
        )
        _log(conn, lead_id, "status_changed", f"{old['status']} -> {new_status}")
    return get_lead_by_id(lead_id)  # type: ignore[return-value]


def update_lead_field(lead_id: str, *, dry_run: bool = False, **fields: Any) -> dict[str, Any]:
    """Update arbitrary lead fields. Auto-updates date_updated. Logs note_added with summary.

    Use update_lead_status for status changes — this function refuses `status` to keep
    the status_since invariant intact.
    """
    if "status" in fields:
        raise ValueError("Use update_lead_status for status changes (status_since invariant)")
    bad = [k for k in fields if k not in _LEAD_FIELDS]
    if bad:
        raise ValueError(f"Unknown lead field(s): {bad}")
    if dry_run:
        return {"would_update": {"id": lead_id, **fields}}
    now = _now()
    sets = ", ".join(f"{k} = ?" for k in fields) + ", date_updated = ?"
    values = list(fields.values()) + [now, lead_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE leads SET {sets} WHERE id = ?", values)
        summary = ", ".join(f"{k}={v!r}" for k, v in fields.items())
        action = _infer_field_action(fields)
        _log(conn, lead_id, action, summary[:200])
    return get_lead_by_id(lead_id)  # type: ignore[return-value]


def _infer_field_action(fields: dict[str, Any]) -> str:
    """Pick the most descriptive activity action for a multi-field update."""
    if "proposal_summary" in fields or "proposal_date" in fields:
        return "proposal_created"
    if "discovery_notes" in fields:
        return "discovery_added"
    if "project_path" in fields:
        return "project_started"
    if "research_notes" in fields or "data_confidence" in fields:
        return "research_updated"
    return "note_added"


def record_follow_up(lead_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Update last_follow_up to now. Does NOT touch status_since (storage.md §7.3)."""
    if dry_run:
        return {"would_update": {"id": lead_id, "last_follow_up": "<now>"}}
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE leads SET last_follow_up = ?, date_updated = ? WHERE id = ?",
            (now, now, lead_id),
        )
        _log(conn, lead_id, "follow_up", "User reported follow-up")
    return get_lead_by_id(lead_id)  # type: ignore[return-value]


def get_stale_leads() -> list[dict[str, Any]]:
    """Leads where (now - MAX(status_since, last_follow_up)) > per-status threshold.

    Threshold comes from config.preferences.statusFollowUpDays. NULL threshold = disabled.
    Custom statuses default to 7 days.
    """
    cfg = get_config()["preferences"]
    thresholds: dict[str, int | None] = cfg.get("statusFollowUpDays", {})
    default_custom = 7
    stale: list[dict[str, Any]] = []
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM leads").fetchall()
    for r in rows:
        threshold = thresholds.get(r["status"], default_custom)
        if threshold is None:
            continue
        anchor_str = r["last_follow_up"] or r["status_since"]
        if r["last_follow_up"] and r["status_since"]:
            anchor_str = max(r["last_follow_up"], r["status_since"])
        anchor = datetime.fromisoformat(anchor_str)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - anchor).days
        if elapsed > threshold:
            row = dict(r)
            row["_days_in_status"] = elapsed
            row["_threshold"] = threshold
            stale.append(row)
    stale.sort(key=lambda r: r["_days_in_status"], reverse=True)
    return stale


def get_overdue_follow_ups(days: int = 5) -> list[dict[str, Any]]:
    """Convenience wrapper: stale leads filtered to status='proposal_sent'."""
    return [r for r in get_stale_leads() if r["status"] == "proposal_sent"]


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def _add_tag_in_conn(
    conn: sqlite3.Connection, lead_id: str, name: str, category: str = "custom"
) -> None:
    name = name.strip().lower()
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        tag_id = row["id"]
    else:
        tag_id = _new_id()
        conn.execute(
            "INSERT INTO tags (id, name, category) VALUES (?, ?, ?)",
            (tag_id, name, category),
        )
    conn.execute(
        "INSERT OR IGNORE INTO lead_tags (lead_id, tag_id) VALUES (?, ?)",
        (lead_id, tag_id),
    )
    _log(conn, lead_id, "tag_added", name)


def add_tag(lead_id: str, name: str, category: str = "custom", *, dry_run: bool = False) -> None:
    if dry_run:
        return
    with get_connection() as conn:
        _add_tag_in_conn(conn, lead_id, name, category)


def remove_tag(lead_id: str, name: str, *, dry_run: bool = False) -> None:
    if dry_run:
        return
    name = name.strip().lower()
    with get_connection() as conn:
        tag = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        if not tag:
            return
        conn.execute(
            "DELETE FROM lead_tags WHERE lead_id = ? AND tag_id = ?",
            (lead_id, tag["id"]),
        )
        _log(conn, lead_id, "tag_removed", name)


def get_tags_for_lead(lead_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT t.* FROM tags t "
            "JOIN lead_tags lt ON lt.tag_id = t.id "
            "WHERE lt.lead_id = ? ORDER BY t.name",
            (lead_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_leads_by_tag(name: str) -> list[dict[str, Any]]:
    name = name.strip().lower()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT l.* FROM leads l "
            "JOIN lead_tags lt ON lt.lead_id = l.id "
            "JOIN tags t ON t.id = lt.tag_id "
            "WHERE t.name = ? ORDER BY l.date_added DESC",
            (name,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def add_task(
    lead_id: str,
    task_name: str,
    *,
    priority: str = "medium",
    due_date: str | None = None,
    notes: str | None = None,
    is_deliverable: bool = False,
    status: str = "todo",
    dry_run: bool = False,
) -> dict[str, Any]:
    now = _now()
    task = {
        "id": _new_id(),
        "lead_id": lead_id,
        "task_name": task_name,
        "status": status,
        "priority": priority,
        "due_date": due_date,
        "notes": notes,
        "is_deliverable": 1 if is_deliverable else 0,
        "date_created": now,
        "date_updated": now,
    }
    if dry_run:
        return {"would_insert": task}
    with get_connection() as conn:
        cols = ", ".join(task.keys())
        ph = ", ".join("?" * len(task))
        conn.execute(f"INSERT INTO tasks ({cols}) VALUES ({ph})", tuple(task.values()))
        _log(conn, lead_id, "task_created", task_name)
    return task


def get_tasks(lead_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE lead_id = ? "
            "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
            "COALESCE(due_date, '9999')",
            (lead_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_pending_tasks(lead_id: str) -> list[dict[str, Any]]:
    return [t for t in get_tasks(lead_id) if t["status"] != "done"]


def update_task_status(task_id: str, status: str, *, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"would_update": {"id": task_id, "status": status}}
    now = _now()
    with get_connection() as conn:
        row = conn.execute("SELECT lead_id, task_name, status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")
        conn.execute(
            "UPDATE tasks SET status = ?, date_updated = ? WHERE id = ?",
            (status, now, task_id),
        )
        action = "task_completed" if status == "done" else "status_changed"
        _log(conn, row["lead_id"], action, f"{row['task_name']}: {row['status']} -> {status}")
        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(updated)


def find_tasks_by_name(lead_id: str, query: str) -> list[dict[str, Any]]:
    """Fuzzy match on task name within a lead's tasks."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE lead_id = ? AND task_name LIKE ? COLLATE NOCASE",
            (lead_id, f"%{query}%"),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_pipeline(format: str = "csv") -> Path:
    """Export all leads (with tags) to ~/.freelance-forge/exports/pipeline-<date>.<ext>."""
    if format not in ("csv", "json"):
        raise ValueError("format must be 'csv' or 'json'")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = get_config_dir() / "exports" / f"pipeline-{today}.{format}"
    with get_connection() as conn:
        leads = [dict(r) for r in conn.execute("SELECT * FROM leads").fetchall()]
        for lead in leads:
            tags = conn.execute(
                "SELECT t.name FROM tags t "
                "JOIN lead_tags lt ON lt.tag_id = t.id WHERE lt.lead_id = ?",
                (lead["id"],),
            ).fetchall()
            lead["tags"] = [t["name"] for t in tags]
    if format == "csv":
        buf = io.StringIO()
        if leads:
            base_fields = [k for k in leads[0] if k != "tags"]
            fieldnames = base_fields + ["tags"]
            writer = csv.DictWriter(buf, fieldnames=fieldnames)
            writer.writeheader()
            for lead in leads:
                row = {k: lead.get(k) for k in base_fields}
                row["tags"] = "|".join(lead["tags"])
                writer.writerow(row)
        out.write_text(buf.getvalue())
    else:
        out.write_text(json.dumps(leads, indent=2))
    return out


def export_lead(lead_id: str, format: str = "json") -> Path:
    """Export a single lead with tags + activity + tasks."""
    if format not in ("csv", "json"):
        raise ValueError("format must be 'csv' or 'json'")
    lead = get_lead_by_id(lead_id)
    if not lead:
        raise ValueError(f"Lead {lead_id} not found")
    bundle = {
        "lead": lead,
        "tags": get_tags_for_lead(lead_id),
        "activity": get_lead_activity(lead_id),
        "tasks": get_tasks(lead_id),
    }
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = "".join(c if c.isalnum() else "-" for c in lead["company"].lower()).strip("-")
    out = get_config_dir() / "exports" / f"{slug}-{today}.{format}"
    if format == "json":
        out.write_text(json.dumps(bundle, indent=2))
    else:
        # Flat CSV for a single lead — useful for pasting into spreadsheets
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["field", "value"])
        for k, v in lead.items():
            writer.writerow([k, v])
        writer.writerow(["tags", "|".join(t["name"] for t in bundle["tags"])])
        out.write_text(buf.getvalue())
    return out


# ---------------------------------------------------------------------------
# CLI shim — keeps SKILL.md files free of inline Python
# ---------------------------------------------------------------------------

def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, default=str))


def _cmd_add_lead(args: argparse.Namespace) -> None:
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    res = add_lead(
        args.company,
        website=args.website,
        contact_name=args.contact_name,
        contact_email=args.contact_email,
        lead_score=args.lead_score,
        data_confidence=args.data_confidence,
        research_notes=args.research_notes,
        pitch_notes=args.pitch_notes,
        suggested_tags=tags or None,
        dry_run=args.dry_run,
    )
    _print_json(res)


def _cmd_get_lead(args: argparse.Namespace) -> None:
    if args.id:
        _print_json(get_lead_by_id(args.id))
    else:
        _print_json(get_lead_by_company(args.company))


def _cmd_search(args: argparse.Namespace) -> None:
    _print_json(search_leads(args.query))


def _cmd_pipeline(args: argparse.Namespace) -> None:
    _print_json(get_leads_by_status(args.status))


def _cmd_stale(_: argparse.Namespace) -> None:
    _print_json(get_stale_leads())


def _cmd_status(args: argparse.Namespace) -> None:
    _print_json(update_lead_status(args.lead_id, args.new_status, dry_run=args.dry_run))


def _cmd_update_field(args: argparse.Namespace) -> None:
    fields = json.loads(args.json)
    _print_json(update_lead_field(args.lead_id, dry_run=args.dry_run, **fields))


def _cmd_follow_up(args: argparse.Namespace) -> None:
    _print_json(record_follow_up(args.lead_id, dry_run=args.dry_run))


def _cmd_tag(args: argparse.Namespace) -> None:
    if args.action == "add":
        add_tag(args.lead_id, args.name, args.category, dry_run=args.dry_run)
    elif args.action == "remove":
        remove_tag(args.lead_id, args.name, dry_run=args.dry_run)
    elif args.action == "list":
        _print_json(get_tags_for_lead(args.lead_id))
    elif args.action == "leads":
        _print_json(get_leads_by_tag(args.name))


def _cmd_task(args: argparse.Namespace) -> None:
    if args.action == "add":
        _print_json(add_task(
            args.lead_id, args.name,
            priority=args.priority, due_date=args.due_date,
            notes=args.notes, is_deliverable=args.deliverable,
            dry_run=args.dry_run,
        ))
    elif args.action == "list":
        _print_json(get_tasks(args.lead_id))
    elif args.action == "pending":
        _print_json(get_pending_tasks(args.lead_id))
    elif args.action == "find":
        _print_json(find_tasks_by_name(args.lead_id, args.name))
    elif args.action == "status":
        _print_json(update_task_status(args.task_id, args.new_status, dry_run=args.dry_run))


def _cmd_activity(args: argparse.Namespace) -> None:
    if args.lead_id:
        _print_json(get_lead_activity(args.lead_id))
    else:
        _print_json(get_recent_activity(args.days))


def _cmd_log(args: argparse.Namespace) -> None:
    log_activity(args.lead_id, args.action, args.details)


def _cmd_export(args: argparse.Namespace) -> None:
    if args.lead_id:
        out = export_lead(args.lead_id, args.format)
    else:
        out = export_pipeline(args.format)
    print(str(out))


def _cmd_config(args: argparse.Namespace) -> None:
    if args.action == "get":
        _print_json(get_config())
    elif args.action == "set":
        _print_json(update_config(args.path.split("."), json.loads(args.value)))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="db_helper")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add-lead")
    a.add_argument("company")
    a.add_argument("--website")
    a.add_argument("--contact-name", dest="contact_name")
    a.add_argument("--contact-email", dest="contact_email")
    a.add_argument("--lead-score", dest="lead_score", type=int)
    a.add_argument("--data-confidence", dest="data_confidence")
    a.add_argument("--research-notes", dest="research_notes")
    a.add_argument("--pitch-notes", dest="pitch_notes")
    a.add_argument("--tags", help="Comma-separated tag names")
    a.add_argument("--dry-run", dest="dry_run", action="store_true")
    a.set_defaults(func=_cmd_add_lead)

    g = sub.add_parser("get-lead")
    g.add_argument("--id")
    g.add_argument("--company")
    g.set_defaults(func=_cmd_get_lead)

    s = sub.add_parser("search")
    s.add_argument("query")
    s.set_defaults(func=_cmd_search)

    pl = sub.add_parser("pipeline")
    pl.add_argument("--status", default=None)
    pl.set_defaults(func=_cmd_pipeline)

    st = sub.add_parser("stale")
    st.set_defaults(func=_cmd_stale)

    us = sub.add_parser("update-status")
    us.add_argument("lead_id")
    us.add_argument("new_status")
    us.add_argument("--dry-run", dest="dry_run", action="store_true")
    us.set_defaults(func=_cmd_status)

    uf = sub.add_parser("update-field")
    uf.add_argument("lead_id")
    uf.add_argument("json", help='JSON object of field updates, e.g. {"proposal_summary": "..."}')
    uf.add_argument("--dry-run", dest="dry_run", action="store_true")
    uf.set_defaults(func=_cmd_update_field)

    fu = sub.add_parser("follow-up")
    fu.add_argument("lead_id")
    fu.add_argument("--dry-run", dest="dry_run", action="store_true")
    fu.set_defaults(func=_cmd_follow_up)

    tg = sub.add_parser("tag")
    tg.add_argument("action", choices=["add", "remove", "list", "leads"])
    tg.add_argument("--lead-id", dest="lead_id")
    tg.add_argument("--name", default="")
    tg.add_argument("--category", default="custom")
    tg.add_argument("--dry-run", dest="dry_run", action="store_true")
    tg.set_defaults(func=_cmd_tag)

    tk = sub.add_parser("task")
    tk.add_argument("action", choices=["add", "list", "pending", "find", "status"])
    tk.add_argument("--lead-id", dest="lead_id")
    tk.add_argument("--task-id", dest="task_id")
    tk.add_argument("--name", default="")
    tk.add_argument("--new-status", dest="new_status", default="todo")
    tk.add_argument("--priority", default="medium")
    tk.add_argument("--due-date", dest="due_date")
    tk.add_argument("--notes")
    tk.add_argument("--deliverable", action="store_true")
    tk.add_argument("--dry-run", dest="dry_run", action="store_true")
    tk.set_defaults(func=_cmd_task)

    ac = sub.add_parser("activity")
    ac.add_argument("--lead-id", dest="lead_id")
    ac.add_argument("--days", type=int, default=7)
    ac.set_defaults(func=_cmd_activity)

    lg = sub.add_parser("log")
    lg.add_argument("lead_id")
    lg.add_argument("action")
    lg.add_argument("--details")
    lg.set_defaults(func=_cmd_log)

    ex = sub.add_parser("export")
    ex.add_argument("--lead-id", dest="lead_id")
    ex.add_argument("--format", default="csv", choices=["csv", "json"])
    ex.set_defaults(func=_cmd_export)

    cf = sub.add_parser("config")
    cf.add_argument("action", choices=["get", "set"])
    cf.add_argument("--path", help='Dotted path, e.g. preferences.pricingStrategy')
    cf.add_argument("--value", help="JSON-encoded value")
    cf.set_defaults(func=_cmd_config)

    pi = sub.add_parser("paths")
    pi.set_defaults(func=lambda _a: _print_json({
        "config_dir": str(get_config_dir()),
        "shared_dir": str(get_shared_dir()),
        "db": str(db_path()),
        "config": str(config_path()),
    }))

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:  # pragma: no cover — CLI surface
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
