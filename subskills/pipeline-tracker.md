# Sub-Skill Deep Dive: Pipeline Tracker

**Parent:** Freelance Forge — `architecture.md`
**Version:** 0.3 — Design Phase (updated for local SQLite storage)
**Date:** 2026-04-26

---

## 1. Purpose

The Pipeline Tracker is the command center of Freelance Forge. It lets the freelancer view, manage, and query their entire pipeline. With local SQLite storage, setup is instant — no authentication, no schema discovery, no configuration.

**Three core functions:**
1. **View** — show pipeline status, summaries, and details
2. **Manage** — update lead stages, add/remove tags, manage follow-ups
3. **Query** — answer any question about the pipeline data (history, stats, filters)

---

## 2. When It Triggers

- "show my pipeline" / "pipeline update" / "pipeline summary"
- "update [client] to [status]" / "mark [client] as [status]"
- "any overdue follow-ups" / "check my follow-ups"
- "tag [client] as [tag]" / "remove [tag] from [client]"
- "what happened with [client]?" / "lead history for [client]"
- "how many leads this month?" / "show my conversion rate"
- "export my pipeline" / "export to CSV"

---

## 3. Setup

### 3.1 First Run

On first use, the database helper creates everything automatically:
1. Create `~/.freelance-forge/` directory and subdirectories
2. Create `pipeline.db` with all tables, indexes, and constraints
3. Create `config.json` with default preferences

No user interaction required. No credentials needed. The user can say "show my pipeline" immediately after install and it works.

### 3.2 What the User Sees

First time: "You don't have any leads yet. Say 'qualify this lead: [company]' to add your first one."

No setup wizard, no configuration screens, no API tokens. Just start using it.

---

## 4. Pipeline Summary

When the user asks to see their pipeline, query the database and present a grouped, scannable digest:

- **Group by status** — each stage as a section
- **Compact** — company name, score (if available), and one relevant data point (proposal date, days since last action, tag)
- **Flag overdue items** — any lead in "proposal_sent" past the follow-up threshold gets a visual indicator
- **Sort within groups** — by lead score descending if available
- **Handle unknown statuses** — if the user has custom status values, show them under their own group rather than hiding them

The follow-up checker (§6) runs automatically as part of the pipeline summary. No separate trigger needed.

---

## 5. Status Updates

Parse the company name and target status from the user's request. Search the database for a matching lead (exact match first, then fuzzy). Present the match for confirmation if ambiguous.

**Special case:** updating to "lost" (or equivalent negative status) requires explicit user confirmation before proceeding. This is a meaningful signal that shouldn't happen by accident.

**Special case:** updating to "active" should check whether tasks exist for this lead. If not, flag it — the Project Onboarder may not have been run yet.

Keep the confirmation output minimal — one line is sufficient.

**Activity log:** Every status change is logged with old status, new status, and timestamp.

---

## 6. Follow-Up System

**Timing:** The follow-up check runs automatically whenever the pipeline summary is shown (§4). It can also be triggered directly ("any overdue follow-ups?").

**No cron for v1.** The user sees overdue items when they check their pipeline. Proactive alerts would require cron setup and risk being annoying. This can be a v2 feature.

**Logic:** Query for leads with status "proposal_sent". Compare their `proposal_date` or `last_follow_up` to the current date. Flag any where the elapsed days exceed the `followUpDays` preference (default: 5). Sort by most overdue first.

**Offer to draft:** For each overdue lead, offer to draft a follow-up email in chat. If the user accepts, read the lead's full row + recent activity for context and write a short, professional follow-up. Tone: helpful, not pushy. Include a clear next step.

---

## 7. Tag Management

**Adding tags:** "tag Acme as urgent", "mark Baker as wordpress", "add referral-john to Smith Plumbing"
- Creates the tag if it doesn't exist
- Optionally categorises: "tag Acme as urgent [category: custom]"
- Logs: `tag_added` in activity_log

**Removing tags:** "remove urgent from Acme", "untag Baker as wordpress"
- Logs: `tag_removed` in activity_log

**Querying by tag:** "show me all wordpress leads", "which leads are tagged urgent?"
- Uses the `lead_tags` junction table
- Can combine with other filters ("show me all wordpress leads that are still in lead status")

---

## 8. Activity History

**Lead history:** "what happened with Acme?"
- Queries `activity_log` for the lead's ID
- Returns chronologically ordered list of all actions
- Presented as a readable timeline, not raw log entries

**Recent activity:** "what happened this week?", "any activity in the last 7 days?"
- Queries `activity_log` by date range
- Groups by lead

**Stats:** "how many leads did I qualify this month?", "what's my conversion rate?"
- Counts actions by type and date range
- Calculates conversion rates between statuses

---

## 9. Query Variants

Beyond the default summary, support these common queries:
- **Filtered by status:** "show me all leads in [status]"
- **Filtered by score:** "show me my best leads" (score above a threshold)
- **Filtered by date:** "leads from this week" (creation date range)
- **Filtered by tag:** "show me all [tag] leads"
- **Single lead detail:** "tell me about [client]" (full row details + recent activity)
- **Search:** "find leads matching [query]" (search across company, contact, notes)
- **Stats/aggregates:** "how many leads this month?", "conversion rate from lead to active"
- **Task queries:** "show me [client]'s tasks", "what's left to do?", "any overdue tasks?"

---

## 10. Task Management

During active projects, the Pipeline Tracker handles day-to-day task operations:

**Viewing tasks:**
- "show me O'Brien's tasks" → all tasks for a lead, sorted by priority then due date
- "what's left to do for O'Brien?" → pending tasks only (status != 'done')
- "any overdue tasks?" → tasks where due_date < today and status != 'done'

**Updating tasks:**
- "mark 'collect brand assets' as done" → update task status
- "move 'design homepage' to in progress" → update task status
- Uses fuzzy matching on task name to find the right task
- Logs `task_completed` or `status_changed` in activity_log

**Adding tasks:**
- "add a task for O'Brien: set up Google Analytics" → create new task with default priority
- "add a high-priority task: client review of homepage" → create with specified priority
- Logs `task_created` in activity_log

---

## 11. Export

**CSV export:** "export my pipeline"
- All leads with their tags as a CSV file
- Saved to `~/.freelance-forge/exports/pipeline-[date].csv`
- Suitable for import into Notion, Google Sheets, Excel

**JSON export:** "export pipeline as JSON"
- Full data including activity log and tasks
- Suitable for backup or programmatic use

**Single lead export:** "export Acme"
- One lead with full context (tags, activity, tasks)

---

## 12. Database Interactions

The Pipeline Tracker uses these database helper functions:
- `get_leads_by_status()` — pipeline summary
- `get_stale_leads()` — follow-up suggestions (status-based, see §6.1)
- `update_lead_status(lead_id, status)` — status updates (auto-updates status_since)
- `record_follow_up(lead_id)` — user-reported follow-up (updates last_follow_up + resets status_since)
- `add_tag(lead_id, tag_name, category)` — tag management
- `remove_tag(lead_id, tag_name)` — tag management
- `get_lead_activity(lead_id)` — history
- `get_recent_activity(days)` — recent activity
- `search_leads(query)` — search
- `get_tasks(lead_id)` / `get_pending_tasks(lead_id)` — task viewing
- `update_task_status(task_id, status)` — task updates
- `add_task(lead_id, task_name, priority)` — task creation
- `export_pipeline(format)` — export
- `log_activity(lead_id, action, details)` — activity logging

It does NOT create leads (that's handled by Lead Qualifier) and does NOT create the initial project task set (that's handled by Project Onboarder). It does manage tasks day-to-day after they're created.

---

## 13. Error Handling Principles

Errors should be helpful and actionable, not just informative. General patterns:

- **Database not found** → create it automatically (this should never surface as an error to the user)
- **Config corrupted** → recreate with defaults, preserve what data can be salvaged
- **Empty pipeline** → "No leads in pipeline. Run Lead Qualifier to add your first lead."
- **Ambiguous company name** → present matching options for disambiguation
- **Lead not found** → "No lead found matching '[name]'. Check the spelling or use 'show my pipeline' to see all leads."
- **Export directory missing** → create it automatically

---

## 14. Design Decisions

### Why No Setup Flow
The entire Notion integration (schema discovery, field mapping, augmentation, config saving) was replaced by a single function call that creates the database. Setup is not a user-facing concept anymore. The database exists or it doesn't — and if it doesn't, it's created. This is the single biggest simplification from the architecture shift.

### Why "Lost" Requires Confirmation
Accidental status changes are easy in chat ("mark Baker as lost" when you meant "qualified"). One extra confirmation prevents data issues.

### Why Follow-Up Is Attached to Pipeline Summary
The natural moment to surface stale leads is when the user is already looking at their pipeline. A separate check requires a separate thought. Passive awareness beats proactive nagging for v1.

### Why Status-Based Follow-Ups (Not Just Post-Proposal)
Freelancers forget to follow up at every stage, not just after sending proposals. A lead gets qualified, they mean to call, a week passes. A discovery call happens, they mean to schedule the next one, another week passes. Checking `status_since` against per-status thresholds catches these gaps regardless of pipeline stage.

### Why The Agent Doesn't Repeat Suggestions
If the agent mentions "follow up with Acme" every time the user asks anything, it becomes noise. The suggestion appears in the pipeline summary (once) and in specific follow-up queries. The user's session context handles the "already mentioned" logic naturally — the LLM knows it already told the user.

### Why Task Management Lives Here
The Project Onboarder creates the initial task set. But day-to-day task management (checking off tasks, adding new ones, seeing what's left) is a pipeline operation. The freelancer checks their pipeline, sees what's active, and manages tasks from there. Splitting task management across two sub-skills would create confusion about who owns what.

### Why No Cron
Cron adds setup complexity and unprompted alerts can feel annoying. The user checks their pipeline when they want to. If they want proactive alerts, that's an easy v2 addition.

### Why Tags Are a First-Class Feature
With Notion gone, we lost the visual kanban board. Tags partially compensate — they give users a way to categorise and filter leads without rigid predefined categories. The agent suggests relevant tags from research; users define their own taxonomy.

---

## 15. Claude Code Implementation Notes

### What's Fixed
- No setup flow — database created automatically on first use
- "Lost" status requires confirmation
- Follow-up check runs as part of pipeline summary, no cron in v1
- Email drafts are chat output only
- Activity logging on every status change and tag operation
- Export to CSV and JSON
- Tag management (add, remove, query)

### What Claude Code Has Freedom On
- The exact SKILL.md structure, wording, and sections
- The specific pipeline summary format (should be compact and scannable, but the exact layout is up to you)
- Fuzzy matching logic for company names
- How to present activity history in chat
- How to present stats and aggregates
- The tone and content of drafted follow-up emails
- Error message wording (should be helpful and actionable — follow the principle, not specific text)
