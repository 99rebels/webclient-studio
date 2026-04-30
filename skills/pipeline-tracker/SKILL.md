---
name: pipeline-tracker
description: View, manage, and query the freelance pipeline. Use when the user asks to show their pipeline, update a lead's status, check follow-ups, manage tags, view lead history, manage project tasks, see stats, or export data. The default entry point for any "what's going on with my leads / projects" question.
---

# 📊 Pipeline Tracker

The command centre. View pipeline state, change statuses, manage tags and tasks, check follow-up suggestions, look up history, and export. No setup flow — the database and config auto-create on first call.

## When to use

Route based on what the user asks:

```
"show my pipeline" / "pipeline summary"     → §A Master view
"show qualified leads" / "show follow-ups" → §A Filtered views
"tell me about <client>" / "<client> details" → §B Deep view
"update <client> to <status>"              → §C Status updates
"any follow-ups needed?" / "any overdue?"  → §D Follow-ups
"tag <client> as <x>" / "show all <tag>"  → §E Tags
"what happened with <client>?" / "history" → §F History
"find leads matching <query>" / "search"   → §G Search
"show <client>'s tasks" / "mark task done" → §H Tasks
"how many leads this month?" / "stats"     → §I Stats
"import CSV" / "import leads" / "upload"   → §K Import
"export my pipeline" / "export to CSV"     → §J Export
"add [company] to my pipeline"           → §L Quick add
```

This skill does **not** create leads through qualification (Lead Qualifier does), but **does** create leads via CSV import (§K). It does **not** create onboarding task sets (Project Onboarder does).

## ⚡ Tools

```bash
SHARED="$WEBCLIENT_STUDIO_CONFIG_DIR/shared"
PYTHONPATH="$SHARED" python3 -m db_helper <command>
```

**⚠️ Path expansion in JSON:** The shell does not expand variables inside single quotes. Always expand paths before inserting into JSON:

```bash
# ❌ Wrong — $VAR stored as literal string
python3 -m db_helper update-field <id> '{"path": "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/foo"}'

# ✅ Right — variable expands before JSON is built
CLIENT_DIR="$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/acme"
python3 -m db_helper update-field <id> '{"path": "'"$CLIENT_DIR"'"}'
```

## Guard clause

Before any section, run:

```bash
python3 -c "import sys,os; os.environ.get('WEBCLIENT_STUDIO_CONFIG_DIR') or exit(1); sys.path.insert(0, os.environ['WEBCLIENT_STUDIO_CONFIG_DIR']+'/shared'); import db_helper" 2>/dev/null && echo OK
```

- **OK** → set `SHARED="$WEBCLIENT_STUDIO_CONFIG_DIR/shared"` and proceed. All `python3 -m` commands assume `PYTHONPATH="$SHARED"`.
- **Fails** → read `$WEBCLIENT_STUDIO_CONFIG_DIR/references/setup.md` (or bundle's `references/setup.md`), execute setup, then return here.

---

## §A. Master View

The default pipeline view. Scannable, compact, action-oriented.

```bash
python3 -m db_helper pipeline
python3 -m db_helper stale
```

**Group by status** in this order:

```
🟢 Active          — currently in progress
🔵 Onboarding       — being set up
🟡 Proposal sent    — awaiting response
🟠 Qualified        — worth pursuing
⚪ Lead             — new, not yet assessed
🔴 Lost             — declined or unresponsive
✅ Complete         — finished projects
```

**Per lead, one line:**
```
<company> — score <X>/10 — <next-action hint>
```

Where `<next-action hint>` is the most useful context:
- Proposal sent, no response: *"proposal sent <N> days ago, no response"*
- Recent follow-up: *"followed up <N> days ago"*
- Stale: *"⚠️ follow up suggested (<N> days in <status>)"*
- Has pending tasks: *"X tasks remaining"*
- New: *"added <date>"*
- Completed: *"completed <date>"*

**Sort within groups:** `lead_score DESC` (highest = top).

**Stale leads:** flag with ⚠️ inline. Mention stale leads **once per session** — don't repeat.

**Compact by default.** One line per lead. No markdown tables (poor Slack/mobile rendering). Structured text with bullet points per status group.

### Filtered views

```bash
python3 -m db_helper pipeline --status <status>
```

Examples: "show qualified leads" → `--status qualified`, "what proposals are out?" → `--status proposal_sent`

**Empty pipeline:** *"No leads yet. Add a company to track (say 'add Acme Plumbing to my pipeline') or qualify a lead ('qualify this lead: <url>')."*

---

## §B. Deep View

The full client dossier. Everything about one lead.

```bash
python3 -m db_helper get-lead --company "<client>"
python3 -m db_helper tag list --lead-id <id>
python3 -m db_helper task pending --lead-id <id>
python3 -m db_helper activity --lead-id <id>
```

**Trigger:** "tell me about <client>", "<client> details", "what do we know about <client>"

### Display format

**Master view** — wrapped in a code block for visual separation from chat:

```
🟢 Active
• Apex Roofing — score 8/10 — 3 tasks remaining
• Beehive Bakery — score 6/10 — 1 task remaining

🟡 Proposal sent
• Cedarwood Dental — score 7/10 — proposal sent 12 days ago, no response

🟠 Qualified
• Maple Street Cafe — score 8/10 — added 2026-04-28

⚪ Lead
• Northstar Accounting — added 2026-04-30

🔴 Lost
• Old Town Deli — score 5/10 — declined 2026-04-20

✅ Complete
• Greenfield Landscaping — score 7/10 — completed 2026-04-10
```

**Deep view** — wrapped in a code block:

```
**Apex Roofing**
📊 Score: 8/10 | 🟢 Active | Added: 2026-04-15 | 📋 Proposal: 2026-04-18 | Confidence: HIGH

📝 Research Notes
<research_notes from db>

⚖️ Pros & Cons
<pitch_notes from db, or "No pitch notes yet">

---

💬 Discovery Notes
<discovery_notes from db, or "No discovery notes yet">

---

📋 Proposal Summary
<proposal_summary from db, or "No proposal yet">

---

🏷️ Tags
<tag1>, <tag2>, <tag3>

---

✅ Pending Tasks (<count>)
- <task 1> [<priority>] <due-date or "no due date">
- ...

---

📜 Recent Activity (last 5)
- <date> — <human-readable action>
- ...
```

Activity translations with emojis for key milestones:
```
lead_created       → "Created"
lead_scored        → "Scored: <details>"
discovery_added    → "Discovery notes added"
proposal_created    → "📝 Proposal created"
status_changed     → "Status: <old> → <new>"
follow_up          → "Followed up"
project_started    → "🚀 Project started"
task_created       → "Task added: <details>"
task_completed     → "✅ Task done: <details>"
note_added         → "Note: <details>"
tag_added / tag_removed → filtered out (shown in Tags section)
```

Filter out `tag_added`/`tag_removed` from activity (shown in Tags section). Use action code translations from §F.

For ambiguous company matches, present all candidates with status + score. Ask the user to pick.

---

## §C. Status Updates

```bash
python3 -m db_helper get-lead --company "<client>"
python3 -m db_helper update-status <lead-id> <new-status>
```

The shim auto-updates `status_since`, `date_updated`, and logs `status_changed`.

**Confirmation required for `lost`:** Show current status and ask: *"Mark Acme as lost? (Status: qualified, score: 7. Data preserved — you can revert later.) [y/N]"* Wait for `y`.

**Special check for `active`:** Before applying, check tasks:
```bash
python3 -m db_helper task list --lead-id <lead-id>
```
If empty: *"This lead has no tasks. Run Project Onboarder first, or confirm you want to set status=active without onboarding."*

For ambiguous matches, present candidates and ask. Don't guess.

Output: `Acme: qualified → proposal_sent.`

---

## §D. Follow-ups

```bash
python3 -m db_helper stale
```

Returns leads where `(now - MAX(status_since, last_follow_up)) > per-status threshold`. Respects `config.preferences.statusFollowUpDays` — `null` means follow-ups disabled (default for `active`, `complete`, `lost`).

Render: *"<Company> — <N> days in <status> (threshold: <T>)"* sorted most overdue first.

Per-row: *"Want a follow-up email draft for Acme?"*

If yes, draft in chat (never auto-send). Use the lead's row + recent activity for context. Tone: helpful, not pushy.

When the user says they followed up:
```bash
python3 -m db_helper follow-up <lead-id>
```
Updates `last_follow_up` only — does **not** touch `status_since`. The follow-up "buys time" without losing status history.

---

## §E. Tags

```bash
python3 -m db_helper tag add --lead-id <id> --name <name> [--category custom|service|source|budget]
python3 -m db_helper tag remove --lead-id <id> --name <name>
python3 -m db_helper tag list --lead-id <id>
python3 -m db_helper tag leads --name <name>
```

Tag names normalised to lowercase. Unknown tags auto-created. Auto-logs `tag_added`/`tag_removed`.

---

## §F. History

```bash
python3 -m db_helper activity --lead-id <id>     # full lead history
python3 -m db_helper activity --days 7           # all leads, last N days
```

Render as chronological timeline. Translate action codes:

```
lead_created    → "Created"
lead_scored     → "Scored: <details>"
discovery_added → "Discovery notes added"
proposal_created → "Proposal created"
status_changed  → "Status: <details>"
follow_up       → "Followed up"
project_started → "Project started"
task_created    → "Task added: <details>"
task_completed  → "Task done: <details>"
note_added      → "Note: <details>"
tag_added / tag_removed → filtered out (shown in Tags section)
```

---

## §G. Search

```bash
python3 -m db_helper search "<query>"
```

Searches across `company`, `contact_name`, `contact_email`, `research_notes`. Case-insensitive `LIKE %query%`. Return all matches.

For company name only, prefer `get-lead --company` (fuzzy, faster, no notes search).

---

## §H. Tasks

```bash
python3 -m db_helper task list --lead-id <id>
python3 -m db_helper task pending --lead-id <id>
python3 -m db_helper task find --lead-id <id> --name "<query>"
python3 -m db_helper task add --lead-id <id> --name "<task>" [--priority high|medium|low] [--due-date YYYY-MM-DD]
python3 -m db_helper task status --task-id <id> --new-status todo|in_progress|done
```

**Updating by name:**
1. `task find --lead-id <id> --name "<user query>"` (fuzzy)
2. 0 results → tell user. 1 → use it. >1 → present and ask.
3. `task status --task-id <found-id> --new-status <status>`

Auto-logs `task_created`, `task_completed`, or `status_changed`.

"What's left to do?" → `task pending`, sort by priority then due date.

"Any overdue?" → fetch pending tasks for all active leads, filter `due_date < today`.

---

## §I. Stats

```bash
python3 -m db_helper activity --days 30
```

Aggregate from the activity log in your response:
- "How many leads this month?" → count `lead_created` in last 30 days
- "Conversion rate?" → leads with `status_changed: lead → qualified` ÷ total `lead_created`
- "How many proposals out?" → `pipeline --status proposal_sent` then count

Be honest about approximation. If not derivable from the log + leads table, say so.

---

## §J. Export

```bash
python3 -m db_helper export --format csv
python3 -m db_helper export --format json
python3 -m db_helper export --lead-id <id> --format json
```

Writes to `$WEBCLIENT_STUDIO_CONFIG_DIR/exports/`. Tell the user the path.

CSV → spreadsheet/Notion (one row per lead, tags pipe-separated). JSON → backup/programmatic (full bundle including tags, activity, tasks).

No confirmation required — read-only on user's own data.

---

## §K. Import

Import leads from CSV into the pipeline. Two-phase flow:

- **Phase 1 (here):** Bulk import — add leads with `imported` tag, `LOW` confidence, `lead` status
- **Phase 2 (Lead Qualifier):** On-demand enrichment — "qualify [company]" detects existing lead, runs research, updates the row

### Flow

**1.** User provides CSV (file path or drops file).

**2.** Read it. If garbled characters (mojibake), try `encoding='latin-1'` or `'cp1252'` (common Windows Excel export).

**3.** Show headers + first 3–5 rows so the user can see what they're working with.

**4.** Propose column mapping:

```
Valid target fields:
company, website, contact_name, contact_email, status,
lead_score, data_confidence, research_notes, pitch_notes, tags
```

Columns that don't match → "skip".

**5.** Preview 3–5 rows. Flag issues (missing required field, invalid score, malformed URL).

**6.** Wait for explicit go-ahead. No auto-import.

**7.** Import row by row. For each row:
```bash
python3 -m db_helper get-lead --company "<company>"
```
- Exists → skip, flag as duplicate
- Doesn't exist →
```bash
python3 -m db_helper add-lead "<Company Name>" \
    --website "<URL>" \
    --contact-name "<name>" \
    --contact-email "<email>" \
    --lead-score <score or omit if NULL> \
    --data-confidence LOW \
    --tags "imported" \
    --research-notes "Imported from <filename> on <date>"
```

Only include flags for mapped fields. For non-`lead` statuses, run `update-status` after adding.

**8.** Summary: total imported, skipped (duplicates), issues.

### Import rules

```
✅ Required:        company — skip and flag rows without it
✅ Default score:   NULL (don't import arbitrary scores)
✅ Default status:  lead
✅ Default tags:    imported
✅ Default confidence: LOW
✅ Validation:      scores 1–10 or NULL, URLs must look like URLs,
                   statuses must be valid
✅ Batch cap:       50 rows max (offer batches for larger files)
✅ Duplicate check: before each add-lead
✅ Audit trail:     copy CSV to imports/ with timestamped filename
```

### What NOT to do

- No auto-import without user confirming the mapping
- No guessing values for unmapped columns
- No overwriting existing leads silently
- No dumping unmapped columns into notes unless explicitly asked
- No creating new DB columns to match their CSV

---

## §L. Quick Add

Add a company to the pipeline without a qualification report. Use when the user wants to track a lead before having time to qualify them.

**Trigger:** "add [company] to my pipeline" (when no qualification report exists)

### Flow

**1.** Check if the company already exists:
```bash
python3 -m db_helper get-lead --company "<Company Name>"
```
If exists: tell the user and offer to show/update.

**2.** Ask for the website URL (if not provided).

**3.** Create a minimal lead row:
```bash
python3 -m db_helper add-lead "<Company Name>" --website "<URL>"
```

**4.** Tell the user: *"Added <Company> as a lead. No qualification report yet — run 'qualify <Company>' when you're ready to research and score them."*

The lead enters with status `lead`, no score, no report. Pipeline Tracker's master view shows it under `⚪ Lead`. When the user eventually runs Lead Qualifier, it detects the existing entry, runs research, and upgrades the status to `qualified`.

---

## 🔒 Error handling

```
Database not found       → Auto-created — should never surface
Empty pipeline           → "No leads yet. Run Lead Qualifier to add your first."
Ambiguous company name   → Present candidates with status + score. Ask user.
Lead not found           → "No lead matching '<name>'. Try 'show my pipeline'."
Export dir missing       → Auto-created
Config corrupted         → Recreate with defaults. Preserve salvageable values.
```

Never print raw shim errors. Translate to actionable language.

## Confirmation rules

```
✅ Needs confirmation:   status → lost, status → active (no tasks)
❌ No confirmation:      status updates (other), tags, tasks, follow-ups, exports
```

## End-of-turn

Mostly a one-line confirmation:

```
✅ "Acme: qualified → proposal_sent."
✅ "Tagged Acme as 'urgent'."
✅ "Exported 12 leads to $WEBCLIENT_STUDIO_CONFIG_DIR/exports/pipeline-2026-04-26.csv."
✅ "Logged follow-up for Acme."
```

## Notes

- **Format output** for the current channel — adapt formatting to match what the platform supports
- **Cross-skill data contract:** reads these fields (written by Lead Qualifier, Proposal Builder, Project Onboarder):
  - `lead_score`, `research_notes`, `pitch_notes`, `data_confidence`, `tags` → from Lead Qualifier
  - `discovery_notes`, `proposal_summary` → from Proposal Builder
  - Tasks → from Project Onboarder
- **Stale leads:** flag once per session, don't repeat
- **Ambiguous matches:** always present candidates and ask, never guess
