# Freelance Forge — Local Storage Specification

**Version:** 0.1
**Date:** 2026-04-26
**Replaces:** Architecture doc §4 (Notion Integration)

---

## 1. Overview

All persistent data for Freelance Forge lives locally in a single directory. There is no external database, no API authentication, no cloud dependency. The agent reads and writes a SQLite database for structured data and markdown files for human-readable reports.

**Why local storage instead of Notion/external CRM:**
- Zero setup — no API keys, no integrations, no auth flows
- No dependency on third-party services, pricing tiers, or API reliability
- Data is fully portable — a single directory the user owns
- Schema is controlled by us — no discovery, mapping, or augmentation complexity
- Reports and metadata live in the same place — coherent audit trail
- Users who want Notion/Sheets can export — one-way, no sync complexity

---

## 2. Directory Structure

```
~/.freelance-forge/
├── pipeline.db                          # SQLite database (structured data)
├── config.json                          # User preferences
└── reports/
    ├── qualifications/
    │   └── acme-plumbing-2026-04-25.md  # Full qualification report
    ├── proposals/
    │   └── acme-plumbing-2026-04-28.md  # Full proposal document
    └── projects/
        └── acme-plumbing/               # Per-client project directory
            ├── project-brief.md
            ├── onboarding-checklist.md
            └── sitemap.md
```

**Environment variables:**
- `FREELANCE_FORGE_CONFIG_DIR` — base directory (default: `~/.freelance-forge/`)
- No other env vars required for storage. No tokens, no API keys.

**Path resolution:**
All sub-skills resolve paths through the config manager. If `FREELANCE_FORGE_CONFIG_DIR` is set, use it. Otherwise, default to `~/.freelance-forge/`. Create the directory and subdirectories on first run if they don't exist.

---

## 3. Database Schema

### 3.1 Leads Table

The central table. One row per lead/client. Replaces the Notion pipeline database.

```sql
CREATE TABLE IF NOT EXISTS leads (
    id              TEXT PRIMARY KEY,          -- UUID, generated on creation
    company         TEXT NOT NULL,             -- Company/client name
    website         TEXT,                      -- Company website URL
    contact_name    TEXT,                      -- Primary contact name
    contact_email   TEXT,                      -- Primary contact email
    status          TEXT NOT NULL DEFAULT 'lead',  -- Pipeline stage
    lead_score      INTEGER,                   -- 1-10 qualification score
    research_quality TEXT,                     -- HIGH/MEDIUM/LOW from Lead Qualifier
    date_added      TEXT NOT NULL,             -- ISO 8601 timestamp
    date_updated    TEXT NOT NULL,             -- ISO 8601, updated on every write
    proposal_date   TEXT,                      -- Date proposal was sent
    last_follow_up  TEXT,                      -- Date of most recent follow-up
    status_since    TEXT NOT NULL,             -- ISO 8601 — when the lead entered its current status
    next_action     TEXT,                      -- What to do next (free text)
    research_notes  TEXT,                      -- Summary from Lead Qualifier (full report is a file)
    discovery_notes TEXT,                      -- User's notes from discovery call
    proposal_summary TEXT,                     -- Summary from Proposal Builder (full proposal is a file)
    project_path    TEXT                       -- Path to project directory in reports/projects/
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(lead_score);
CREATE INDEX IF NOT EXISTS idx_leads_proposal_date ON leads(proposal_date);
CREATE INDEX IF NOT EXISTS idx_leads_company ON leads(company);
CREATE INDEX IF NOT EXISTS idx_leads_status_since ON leads(status_since);
```

**Default status values:** `lead`, `qualified`, `proposal_sent`, `onboarding`, `active`, `complete`, `lost`

These are configurable in `config.json`. The user can add custom statuses. The database stores whatever string is set — there's no constraint enforcement on the values (flexibility over rigidity).

**`status_since`:** Set to the current timestamp whenever the lead's status changes. This enables the follow-up suggestion system — if a lead has been in a status longer than the configured threshold, it's flagged as potentially needing attention. See §7.2.

### 3.2 Tags Table + Junction Table

Replaces Notion's fixed select properties (Budget Range, Service Type, Source). Tags are user-defined and unlimited.

```sql
CREATE TABLE IF NOT EXISTS tags (
    id          TEXT PRIMARY KEY,          -- UUID
    name        TEXT UNIQUE NOT NULL,      -- e.g. "wordpress", "referral-john", "urgent"
    category    TEXT                       -- Optional grouping: "service", "source", "budget", "custom"
);

CREATE TABLE IF NOT EXISTS lead_tags (
    lead_id     TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    tag_id      TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (lead_id, tag_id)
);
```

**How tags replace the old Notion properties:**
- `Budget Range` select → tags with category "budget" (e.g. "£1-3K", "£3-5K", "unknown")
- `Service Type` multi_select → tags with category "service" (e.g. "website-redesign", "new-site", "ecommerce")
- `Source` select → tags with category "source" (e.g. "referral", "google", "linkedin")
- Anything else the user wants to track → tags with category "custom"

**Tag operations:**
- When the Lead Qualifier creates a lead, it can suggest tags based on research (e.g., "wordpress", "local-business")
- The user can add/remove tags at any time via natural language ("tag Acme as urgent")
- Tags are queried like anything else ("show me all wordpress leads")

### 3.3 Activity Log

Records every significant action the agent takes on a lead. This is the audit trail — not possible with Notion integration.

```sql
CREATE TABLE IF NOT EXISTS activity_log (
    id          TEXT PRIMARY KEY,          -- UUID
    lead_id     TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    action      TEXT NOT NULL,             -- Action type (see below)
    details     TEXT,                      -- Human-readable context
    created_at  TEXT NOT NULL              -- ISO 8601 timestamp
);

CREATE INDEX IF NOT EXISTS idx_activity_lead ON activity_log(lead_id);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at);
```

**Action types (predefined, extensible):**
- `lead_created` — Lead Qualifier created a new lead
- `lead_scored` — Lead Qualifier scored a lead
- `research_updated` — Lead research notes updated
- `discovery_added` — Discovery notes added (user input)
- `proposal_created` — Proposal Builder generated a proposal
- `proposal_sent` — Proposal status updated to sent
- `status_changed` — Any status change (details includes old and new status)
- `follow_up` — Follow-up drafted or sent by user
- `project_started` — Project Onboarder created project
- `task_created` — Task added to project
- `task_completed` — Task marked as done
- `tag_added` — Tag added to lead
- `tag_removed` — Tag removed from lead
- `note_added` — Any note added to the lead

**Every sub-skill writes to the activity log.** This is non-negotiable. Every INSERT, UPDATE, or meaningful action gets a corresponding activity_log entry. The user can ask "what happened with Acme?" and get a full history.

### 3.4 Tasks Table

Per-lead project tasks. Replaces the per-client Notion project database.

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,          -- UUID
    lead_id         TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    task_name       TEXT NOT NULL,             -- Task/milestone name
    status          TEXT NOT NULL DEFAULT 'todo',  -- todo, in_progress, done
    priority        TEXT DEFAULT 'medium',     -- high, medium, low
    due_date        TEXT,                      -- ISO 8601 or NULL
    notes           TEXT,                      -- Task details
    is_deliverable  INTEGER DEFAULT 0,         -- 0 = false, 1 = true
    date_created    TEXT NOT NULL,             -- ISO 8601
    date_updated    TEXT NOT NULL              -- ISO 8601
);

CREATE INDEX IF NOT EXISTS idx_tasks_lead ON tasks(lead_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
```

**Default task statuses:** `todo`, `in_progress`, `done`

**Default priorities:** `high`, `medium`, `low`

Both configurable in `config.json`.

**Cascading deletes:** When a lead is deleted, all associated tags, activity log entries, and tasks are automatically deleted (`ON DELETE CASCADE`).

---

## 4. Config File

Stored at `$FREELANCE_FORGE_CONFIG_DIR/config.json`. Minimal — just user preferences. No tokens, no database IDs, no field mappings.

```json
{
  "preferences": {
    "currency": "GBP",
    "followUpDays": 5,
    "statusFollowUpDays": {
      "lead": 5,
      "qualified": 7,
      "proposal_sent": 5,
      "onboarding": 10,
      "active": null
    },
    "defaultStatuses": ["lead", "qualified", "proposal_sent", "onboarding", "active", "complete", "lost"],
    "defaultPriorities": ["high", "medium", "low"],
    "defaultTaskStatuses": ["todo", "in_progress", "done"],
    "pricingStrategy": null
  }
}
```

**Fields:**
- `currency` — used in proposal pricing. Default: "GBP"
- `followUpDays` — days after proposal before flagging as overdue (backward-compatible alias for `statusFollowUpDays.proposal_sent`). Default: 5
- `statusFollowUpDays` — per-status follow-up thresholds in days. When a lead has been in a status longer than its threshold, it's flagged as "follow up suggested" in the pipeline summary. `null` means no follow-up suggestion for that status. See §7.2 for the full follow-up suggestion system.
- `defaultStatuses` — pipeline stages shown in summaries. User can add custom ones.
- `defaultPriorities` — task priority options.
- `defaultTaskStatuses` — task status options.
- `pricingStrategy` — set by Proposal Builder on first use. Values: "day_rate", "project_based", "value_based", "tiered", null (use market ranges)

**Config creation:** Created automatically on first run with defaults. The user never has to manually create or edit this file — the agent handles it.

---

## 5. Database Helper Module

A Python module (`scripts/db_helper.py`) that all sub-skills use to interact with the database. This is the only code that touches SQLite directly — sub-skill SKILL.md files reference this module, not raw SQL.

### 5.1 Responsibilities

- Create database and tables if they don't exist (first-run setup)
- Open/close connections (context manager pattern)
- CRUD operations for leads, tags, tasks, activity log
- Query helpers for common patterns (filter by status, find overdue, search by name)
- Export to CSV/JSON
- Config file read/write
- Path resolution (env var with default)

### 5.2 Key Design Decisions

**Context manager for connections:**
```python
with get_connection() as conn:
    conn.execute("INSERT INTO leads ...")
```
Ensures connections are always closed, even on errors. No dangling connections.

**UUID primary keys:**
All IDs are UUIDs (text format), generated by the helper. This means:
- No auto-increment gaps
- IDs are safe to use in file names and URLs
- No dependency on SQLite's rowid behavior

**`date_updated` is automatic:**
Every `UPDATE` on the leads table sets `date_updated = CURRENT_TIMESTAMP`. Sub-skills don't need to remember to update it.

**`status_since` is automatic:**
Every status change sets `status_since = CURRENT_TIMESTAMP` alongside `date_updated`. This enables the follow-up suggestion system (see §7.2).

**Dry-run option:**
A `dry_run=True` parameter on write operations (INSERT, UPDATE, DELETE). When enabled, the function returns what *would* be written without actually writing it. Useful for:
- First-time setup ("here's what I'm about to do to your database, confirm?")
- User confidence ("show me the update before you make it")

**Graceful degradation:**
If the database file doesn't exist, create it. If a table is missing, create it. If the config file doesn't exist, create it with defaults. The user should never see a "database not found" error.

### 5.3 Query Patterns

The helper provides functions for common queries. Sub-skills call these functions; they don't write raw SQL.

**Fuzzy match definition:**
Case-insensitive `LIKE %query%` on `company` (and `task_name` for tasks). If multiple rows match, return all candidates so the caller can disambiguate. No Levenshtein distance or phonetic matching in v1 — the query complexity doesn't warrant it at freelancer scale.

**Pipeline summary:**
```python
get_leads_by_status()          # Returns leads grouped by status
get_leads_sorted_by_score()    # All leads sorted by score descending
```

**Follow-up checking:**
```python
get_stale_leads()              # Leads past their per-status threshold (uses MAX(status_since, last_follow_up))
get_overdue_follow_ups(days=5) # Convenience: same check filtered to status='proposal_sent'
```

**Task management:**
```python
get_tasks(lead_id)             # All tasks for a project
add_task(lead_id, task_name, ...)  # Add a new task
update_task_status(task_id, status)  # Mark task as done/in_progress
get_pending_tasks(lead_id)     # Tasks where status != 'done'
```

**Lead lookup:**
```python
get_lead_by_company(name)      # Exact match first, then fuzzy
get_lead_by_id(lead_id)        # Direct lookup
search_leads(query)            # Search across company, contact, notes
```

**Activity log:**
```python
get_lead_activity(lead_id)     # Full history for one lead
get_recent_activity(days=7)    # All activity in time range
```

**Tags:**
```python
add_tag(lead_id, tag_name, category="custom")
remove_tag(lead_id, tag_name)
get_leads_by_tag(tag_name)
get_tags_for_lead(lead_id)
```

**Export:**
```python
export_pipeline(format="csv")  # All leads as CSV
export_pipeline(format="json") # All leads as JSON
export_lead(lead_id, format="csv")  # Single lead with all data
```

### 5.4 Export Format

**CSV export (pipeline):**
```
company,status,lead_score,website,contact_email,date_added,proposal_date,tags
Acme Plumbing,qualified,7,acmeplumbing.ie,joe@acme.ie,2026-04-25,,wordpress|local-business
```

**JSON export (single lead with full context):**
```json
{
  "lead": { ... },
  "tags": [ ... ],
  "activity": [ ... ],
  "tasks": [ ... ]
}
```

CSV for spreadsheet import (Notion, Google Sheets, Excel). JSON for programmatic access or backup.

---

## 6. Data Integrity

### 6.1 Atomicity

SQLite uses transactions. Every write operation in the helper should be wrapped in a transaction:
```python
conn.execute("BEGIN")
# ... operations ...
conn.execute("COMMIT")
```

If any operation fails, the entire transaction rolls back. No partial writes, no corrupted state.

### 6.2 Foreign Keys

Foreign keys are enforced (`PRAGMA foreign_keys = ON`). This means:
- A task cannot reference a non-existent lead
- A tag cannot be attached to a non-existent lead
- Deleting a lead cascades to tags, tasks, and activity (no orphans)

### 6.3 Backups

The database is a single file. Users can back it up by copying `pipeline.db`. The helper provides no automatic backup mechanism in v1 — the user owns their data and can copy the file. A backup helper could be added in v2.

### 6.4 No Data Deletion by the Agent

The agent can update status to "lost" but should never execute a `DELETE` on a lead row. Lost leads stay in the database — they have history and research that might be valuable later. If a user explicitly asks to delete a lead, confirm before proceeding.

---

## 7. User Querying

### 7.1 The Agent IS the Query Interface

Users don't write SQL. They say things like:
- "show my pipeline"
- "how many leads did I qualify this month?"
- "what happened with Acme?"
- "show me all overdue follow-ups"
- "which leads scored 8 or above?"
- "show me all wordpress leads that are still in lead status"

The agent translates these to function calls on the helper module. The helper provides the query patterns; the SKILL.md instructions teach the agent when and how to use them.

### 7.2 Built-in Query Types

The Pipeline Tracker supports these query types out of the box:
- **Pipeline summary** — all leads grouped by status, sorted by score, with follow-up suggestions
- **Status filter** — "show me all leads in [status]"
- **Score filter** — "show me my best leads" (above a threshold)
- **Date filter** — "leads from this week/month"
- **Single lead detail** — "tell me about [client]" (full row + recent activity)
- **Follow-up suggestions** — "any leads I should follow up on?" (see §7.4)
- **Tag filter** — "show me all [tag] leads"
- **Lead history** — "what happened with [client]?" (activity log)
- **Search** — find leads by name, contact, or notes content (LIKE queries, not FTS)
- **Aggregate stats** — "how many leads this month?", "conversion rate from lead to active"
- **Task queries** — "show me O'Brien's tasks", "what's left to do?" (see §7.5)

### 7.3 Follow-Up Suggestion System

**The problem:** Freelancers forget to follow up. A lead gets qualified, the freelancer means to call them, a week passes, nothing happens. Same for post-proposal follow-ups, onboarding check-ins, etc.

**How it works:** The database tracks how long each lead has been in its current status via the `status_since` field. The Pipeline Tracker checks these durations against configurable per-status thresholds defined in `config.json` under `statusFollowUpDays`.

**Default thresholds:**
| Status | Threshold | Meaning |
|---|---|---|
| `lead` | 5 days | Qualified but no contact made — suggest reaching out |
| `qualified` | 7 days | Contacted but no discovery call yet — suggest scheduling one |
| `proposal_sent` | 5 days | Proposal sent but no response — suggest following up |
| `onboarding` | 10 days | Project started but stalled — suggest checking in with client |
| `active` | null (disabled) | Active projects are managed via tasks, not follow-ups |
| `complete` | null (disabled) | |
| `lost` | null (disabled) | |

**The query:** `get_stale_leads()` returns all leads where `(current_date - MAX(status_since, last_follow_up)) > threshold` for their status. If `last_follow_up` is NULL, only `status_since` is used.

**How the agent presents it:**
- When showing the pipeline summary, stale leads get a visual indicator: `⚠️ follow up suggested (7 days in qualified)`
- The agent mentions stale leads once per pipeline summary: "A few leads might need attention: Acme (5 days in lead), Baker (7 days in qualified)."
- The agent does NOT repeat the suggestion in subsequent messages within the same session — the user already saw it
- If the user asks specifically ("any follow-ups needed?"), the agent provides the full stale leads list regardless

**When the threshold resets:**
- A status change resets `status_since` to now (the only thing that changes it)
- A user-reported follow-up updates `last_follow_up` to now — `status_since` is NOT changed
- The stale check uses `MAX(status_since, last_follow_up)` against the threshold, not `status_since` alone
- This means a follow-up buys the freelancer time within the same status without losing the status history

**Custom thresholds:** Users can set their own thresholds via config or by telling the agent ("remind me about leads after 3 days"). Custom statuses get a default threshold of 7 days unless configured.

### 7.4 Task Queries

During active projects, the freelancer manages tasks through the Pipeline Tracker:
- "show me O'Brien's tasks" → `get_tasks(lead_id)`
- "mark 'collect brand assets' as done" → `update_task_status(task_id, 'done')`
- "add a task: set up analytics" → `add_task(lead_id, 'Set up analytics', ...)`
- "what's left to do for O'Brien?" → `get_pending_tasks(lead_id)`
- "show me all overdue tasks" → filter tasks where `due_date < today AND status != 'done'`

### 7.5 Export for External Use

Users who want their data in Notion, Google Sheets, or any other tool:
- `export_pipeline(format="csv")` → import into Notion/Sheets/Excel
- `export_pipeline(format="json")` → use programmatically or as backup

This is one-way export. No sync, no two-way updates, no conflict resolution. The user exports when they want to, imports wherever they want to.

---

## 8. Migration from Notion (if anyone asks)

If a future user asks "can I import my existing Notion pipeline?", the answer is: export from Notion as CSV, and we write a one-time import script that maps Notion columns to our schema. This is a v2 feature — not in scope for v1. The import script would:
1. Read the Notion CSV export
2. Map columns to our fields (user confirms mapping)
3. Import rows into the leads table
4. Create tags from select/multi-select columns
5. Log the import in the activity log

Not building this now, but the schema supports it cleanly.
