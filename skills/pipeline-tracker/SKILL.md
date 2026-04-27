---
name: pipeline-tracker
description: View, manage, and query the freelance pipeline. Use when the user asks to show their pipeline, update a lead's status, check follow-ups, manage tags, view lead history, manage project tasks, see stats, or export data. The default entry point for any "what's going on with my leads / projects" question.
---

# Pipeline Tracker

The command centre. View pipeline state, change statuses, manage tags and tasks, check follow-up suggestions, look up history, and export. No setup flow — the database and config auto-create on first call.

## When to use this skill

The Pipeline Tracker handles a wide range of intents. Route based on what the user actually asked:

| User says | Section |
|---|---|
| "show my pipeline" / "pipeline summary" | §A Master view |
| "show qualified leads" / "show follow-ups" / "show lost" | §A Filtered views |
| "tell me about <client>" / "<client> details" / "what do we know about <client>" | §B Deep view |
| "update <client> to <status>" / "mark <client> as <status>" | §C Status updates |
| "any follow-ups needed?" / "any overdue?" | §D Follow-ups |
| "tag <client> as <x>" / "remove <tag> from <client>" / "show all <tag> leads" | §E Tags |
| "what happened with <client>?" / "lead history" / "what happened this week?" | §F History |
| "find leads matching <query>" / "search for <x>" | §G Search |
| "show <client>'s tasks" / "mark <task> done" / "add task" / "what's left to do?" | §H Tasks |
| "how many leads this month?" / "conversion rate" | §I Stats |
| "export my pipeline" / "export to CSV / JSON" | §J Export |

This skill does **not** create new leads (Lead Qualifier does) and does **not** create the initial onboarding task set (Project Onboarder does). It manages everything day-to-day after.

## Tools

```bash
SHARED="${FREELANCE_FORGE_CONFIG_DIR:-$HOME/.freelance-forge}/shared"
PYTHONPATH="$SHARED" python3 -m db_helper <command>
```

## First Run Check

Before any section below, run the guard clause:
```bash
python3 -c "import sys; sys.path.insert(0, '$HOME/.freelance-forge/shared'); import db_helper" 2>/dev/null && echo OK
```

If `OK` — proceed.

If it fails — read `~/.freelance-forge/references/setup.md` and execute the setup steps. Once setup completes, return here.

---

## §A. Master view

The default pipeline view. Scannable, compact, action-oriented.

```
python3 -m db_helper pipeline
python3 -m db_helper stale
```

### Display format

**Group by status.** Use these status groups in this order:
- 🟢 Active — currently in progress
- 🔵 Onboarding — being set up
- 🟡 Proposal sent — awaiting response
- 🟠 Qualified — worth pursuing
- ⚪ Lead — new, not yet assessed
- 🔴 Lost — declined or unresponsive
- ✅ Complete — finished projects
- Custom statuses — group under their own header if they exist

**Per lead, one line:**
```
<company> — score <X>/10 — <next-action hint>
```

Where `<next-action hint>` is the most useful piece of context:
- If proposal sent and no response: *"proposal sent <N> days ago, no response"*
- If last follow-up was recent: *"followed up <N> days ago"*
- If stale: *"⚠️ follow up suggested (<N> days in <status>)"*
- If has pending tasks: *"X tasks remaining"*
- If new: *"added <date>"*
- If completed: *"completed <date>"*

**Sort within groups:** by `lead_score DESC` (highest score = most promising = top).

**Stale leads:** flag with ⚠️ inline. Mention stale leads **once per session** — don't repeat the suggestion in subsequent messages.

**Compact by default.** One line per lead. No markdown tables (they render poorly in Slack and on mobile). Use structured text with bullet points per status group.

### Filtered views

When the user asks for a specific status or category, show only that group using the same format:

```
python3 -m db_helper pipeline --status <status>
```

Examples:
- "show my qualified leads" → `pipeline --status qualified`
- "what proposals are out?" → `pipeline --status proposal_sent`
- "show lost leads" → `pipeline --status lost`
- "any follow-ups needed?" → delegates to §D Follow-ups

### Empty pipeline

*"No leads in pipeline yet. Say 'qualify this lead: <company>' to add your first one."*

---

## §B. Deep view

The full client dossier. Everything we know about one lead in one place.

```
python3 -m db_helper get-lead --company "<client>"
python3 -m db_helper tag list --lead-id <id>
python3 -m db_helper task pending --lead-id <id>
python3 -m db_helper activity --lead-id <id>
```

**Trigger:** "tell me about <client>", "<client> details", "what do we know about <client>", or when the user selects a lead from the master view.

### Display format

```
**<Company Name>**
Score: <X>/10 | Status: <status> | Added: <date> | Quality: <research_quality>

**Research Notes**
<research_notes from db>

**Discovery Notes**
<discovery_notes from db, or "No discovery notes yet">

**Proposal Summary**
<proposal_summary from db, or "No proposal yet">

**Tags**
<tag1>, <tag2>, <tag3>

**Pending Tasks** (<count>)
- <task 1> [<priority>] <due-date or "no due date">
- <task 2> [<priority>] <due-date or "no due date">
(or "No pending tasks")

**Recent Activity** (last 5)
- <date> — <human-readable action>
- <date> — <human-readable action>
...
```

Use the action code translations from §F (History) to make activity readable.

For ambiguous matches on `<client>`, present all candidates with status + score and ask the user to pick. Don't guess.

---

## §C. Status updates

```
python3 -m db_helper get-lead --company "<client>"
python3 -m db_helper update-status <lead-id> <new-status>
```

The shim auto-updates `status_since` and `date_updated`, and logs `status_changed` with old/new in `details`.

**Confirmation required for `lost`** (architecture §9). Show the lead's current status and ask: *"Mark Acme as lost? (Status: qualified, score: 7. Data is preserved — you can revert later.) [y/N]"* Wait for `y`. Anything else cancels.

**Special check for `active`:** before applying, fetch tasks:
```
python3 -m db_helper task list --lead-id <lead-id>
```
If empty, flag: *"This lead has no tasks. Run Project Onboarder first to set up the project, or confirm you want to set status=active without onboarding."*

For ambiguous matches on `<client>`, present all candidates and ask the user to pick. Don't guess.

Output one line on success: `Acme: qualified → proposal_sent.`

---

## §D. Follow-ups

```
python3 -m db_helper stale
```

Returns leads where `(now - MAX(status_since, last_follow_up)) > per-status threshold`. The query already respects per-status thresholds from `config.preferences.statusFollowUpDays` — `null` means follow-ups disabled for that status (default for `active`, `complete`, `lost`).

Render as: *"<Company> — <N> days in <status> (threshold: <T>)"* sorted most overdue first.

Per-row offer: *"Want a follow-up email draft for Acme?"*

If yes, draft in chat (never auto-send). Use the lead's full row + recent activity for context (`db_helper activity --lead-id <id>`). Tone: helpful, not pushy. Specific reference to what's pending. Clear next step.

When the user says they followed up:
```
python3 -m db_helper follow-up <lead-id>
```
This updates `last_follow_up` only — it does **not** touch `status_since`. The next staleness check uses `MAX(status_since, last_follow_up)`, so the follow-up "buys time" without losing the underlying status history (storage.md §7.3).

---

## §E. Tags

```
python3 -m db_helper tag add --lead-id <id> --name <name> [--category custom|service|source|budget]
python3 -m db_helper tag remove --lead-id <id> --name <name>
python3 -m db_helper tag list --lead-id <id>
python3 -m db_helper tag leads --name <name>
```

Tag names are normalised to lowercase. Unknown tags are auto-created. The shim auto-logs `tag_added` / `tag_removed`.

Combine with other queries by chaining: pipeline view → filter the rows by tag in your output. The shim doesn't compose filters in v1.

---

## §F. History

```
python3 -m db_helper activity --lead-id <id>          # full lead history
python3 -m db_helper activity --days 7                # all leads, last N days
```

Render as a chronological timeline grouped by lead (when querying recent), or strict chronological order (when querying one lead). Translate raw action codes to human language:
- `lead_created` → "Created"
- `lead_scored` → "Scored: <details>"
- `discovery_added` → "Discovery notes added"
- `proposal_created` → "Proposal created"
- `status_changed` → "Status: <details>"
- `follow_up` → "Followed up"
- `project_started` → "Project started"
- `task_created` → "Task added: <details>"
- `task_completed` → "Task done: <details>"
- `tag_added` / `tag_removed` → "Tagged / Untagged: <details>"
- `note_added` → "Note: <details>"

---

## §G. Search

```
python3 -m db_helper search "<query>"
```

Searches across `company`, `contact_name`, `contact_email`, `research_notes`. Case-insensitive `LIKE %query%`. Return all matches; don't pre-filter.

For specific lookups by company name only, prefer `get-lead --company` (also fuzzy, faster, no notes search).

---

## §H. Tasks

```
python3 -m db_helper task list --lead-id <id>
python3 -m db_helper task pending --lead-id <id>
python3 -m db_helper task find --lead-id <id> --name "<query>"
python3 -m db_helper task add --lead-id <id> --name "<task>" [--priority high|medium|low] [--due-date YYYY-MM-DD]
python3 -m db_helper task status --task-id <id> --new-status todo|in_progress|done
```

**Updating by name:**
1. `task find --lead-id <id> --name "<user query>"` (fuzzy match)
2. If 0 results → tell user. If 1 → use it. If >1 → present the candidates and ask.
3. `task status --task-id <found-id> --new-status <status>`

The shim auto-logs `task_created`, `task_completed` (when status → `done`), or `status_changed` for other transitions.

**"What's left to do for <client>?"** → use `task pending`. Sort by priority (high first) then due date.

**"Any overdue tasks?"** → fetch all leads' pending tasks and filter where `due_date < today`. The shim doesn't have a single command for this — query per active lead.

---

## §I. Stats

For counts, query the activity log:

```
python3 -m db_helper activity --days 30
```

Then aggregate in your response. Examples:
- "How many leads this month?" → count `lead_created` actions in the last 30 days.
- "Conversion rate from lead to active?" → distinct lead_ids that ever had `status_changed: lead -> qualified` divided by total `lead_created` (approximate; the activity log is the source of truth).
- "How many proposals out?" → `pipeline --status proposal_sent` then count.

Be honest about approximation. If a stat would require multiple queries, do them; if it's not derivable from the activity log + leads table, say so.

---

## §J. Export

```
python3 -m db_helper export --format csv
python3 -m db_helper export --format json
python3 -m db_helper export --lead-id <id> --format json
```

Writes to `$FREELANCE_FORGE_CONFIG_DIR/exports/`. The CLI prints the output path. Tell the user where it landed.

CSV is for spreadsheet/Notion/Sheets import (one row per lead, tags pipe-separated). JSON is for backup or programmatic use (full lead bundle including tags, activity, tasks).

Confirmation is **not** required for export — it's a read-only operation on the user's own data.

---

## Error handling

The principles (pipeline-tracker.md §13):

| Situation | Response |
|---|---|
| Database not found | Auto-created — should never surface. |
| Empty pipeline | "No leads in pipeline. Run Lead Qualifier to add your first." |
| Ambiguous company name | Present matching candidates with status + score. Ask user to pick. |
| Lead not found | "No lead matching '<name>'. Try `show my pipeline` to see all." |
| Export directory missing | Auto-created. |
| Config file corrupted | Recreate with defaults. Preserve any salvageable values. |

Never just print the raw error from the shim. Translate to actionable language.

## What requires confirmation

- Status update to `lost` (§C)
- Status update to `active` when no tasks exist (§C — flag, then confirm)
- Deleting a lead (the shim doesn't expose this — refer the user to manual `sqlite3` if they really want to)

Otherwise: status updates, tag changes, task updates, follow-ups, exports — no confirmation needed.

## End-of-turn

Mostly a one-line confirmation. Examples:
- After master view: just the digest, plus a "next?" hook only if there are stale leads worth highlighting.
- After deep view: the full dossier. Offer relevant actions: "Want to update status, add a task, or draft a follow-up email?"
- After status update: `Acme: qualified → proposal_sent.`
- After tag: `Tagged Acme as 'urgent'.`
- After export: `Exported 12 leads to ~/.freelance-forge/exports/pipeline-2026-04-26.csv.`
- After follow-up logged: `Logged follow-up for Acme. Next stale check uses today as the anchor.`
