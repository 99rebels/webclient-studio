---
name: project-onboarder
description: Turn a signed proposal into a running project. Use when the user says a client signed, accepted, or is ready to start. Creates project tasks in the database, generates a project brief, an onboarding checklist, and a draft sitemap, then sets the lead's status to active.
---

# 🚀 Project Onboarder

Take a client whose proposal was accepted and produce the four things needed to run the project: a brief, a checklist, a draft sitemap, and the initial set of tasks. This is the bridge between "sold" and "building."

## When to use

- "set up project for <client>"
- "onboard <client>"
- "start project for <client>"
- "<client> signed the proposal"
- "they said yes" (when a recent proposal exists)
- "we're good to go with <client>"

## ⚡ Tools

```bash
SHARED="$WEBCLIENT_STUDIO_CONFIG_DIR/shared"
PYTHONPATH="$SHARED" python3 -m db_helper <command>
PYTHONPATH="$SHARED" python3 -m templates render <path> --json '...'
```

**⚠️ Path expansion in JSON:** The shell does not expand variables inside single quotes. Always expand before inserting:

```bash
# ❌ Wrong — $VAR stored as literal
python3 -m db_helper update-field <id> '{"path": "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/foo"}'

# ✅ Right — variable expands first
CLIENT_DIR="$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/acme"
python3 -m db_helper update-field <id> '{"path": "'"$CLIENT_DIR"'"}'
```

## Guard clause

Before the flow, run:

```bash
python3 -c "import sys,os; os.environ.get('WEBCLIENT_STUDIO_CONFIG_DIR') or exit(1); sys.path.insert(0, os.environ['WEBCLIENT_STUDIO_CONFIG_DIR']+'/shared'); import db_helper" 2>/dev/null && echo OK
```

- **OK** → set `SHARED="$WEBCLIENT_STUDIO_CONFIG_DIR/shared"` and proceed. All `python3 -m` commands assume `PYTHONPATH="$SHARED"`.
- **Fails** → read `$WEBCLIENT_STUDIO_CONFIG_DIR/references/setup.md` (or bundle's `references/setup.md`), execute setup, then return here.

## 🔄 Flow

### 1. Find the lead

```bash
python3 -m db_helper get-lead --company "<client>"
```

| Result | Action |
|---|---|
| One match | Continue with that lead row |
| Multiple matches | Present with id, status, score. Ask user to pick |
| No match | Check for a qualification report (below) |

**No match — check for qualification report:**

```bash
ls "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/qualifications/*<client-slug>* 2>/dev/null
ls "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/clients/<client-slug>/<client-slug>* 2>/dev/null
```

**If found:** Auto-add the lead to the pipeline. Capture the actual filename from the glob, create the client folder, move the report, and store the paths:

```bash
mkdir -p "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<client-slug>"
mv "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/qualifications/*<client-slug>* \
   "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/clients/<client-slug>/"

python3 -m db_helper add-lead "<Company Name>" \
    --website "<URL from report>" \
    --lead-score <score from report> \
    --data-confidence <from report> \
    --research-notes "<summary from report>" \
    --pitch-notes "<pros/cons extracted from report>" \
    --tags "<from report>" \
    --client-dir-path "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<client-slug>" \
    --qualification-report-path "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<client-slug>/<actual-filename>"
```

Then proceed.

**If not found:** "No lead matching '<client>'. Run Lead Qualifier first or provide the company name."

Once you have the lead row, fetch tags and check for report paths:

```bash
python3 -m db_helper tag list --lead-id <lead-id>
```

Check the row for:
- `qualification_report_path` — read the qualification report if the path exists
- `proposal_report_path` — read the proposal if the path exists

**If paths are null** (legacy lead): Auto-migrate by searching flat directories:

```bash
ls "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/qualifications/*<company-slug>* 2>/dev/null
ls "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/proposals/*<company-slug>* 2>/dev/null
```

If found: create client folder, move them, store paths. If not: proceed without reports.

### 2. Check for existing tasks

```bash
python3 -m db_helper task list --lead-id <lead-id>
```

If tasks exist: *"This client has N existing tasks. Add the new onboarding tasks, or start fresh? (Starting fresh keeps old tasks — I won't delete anything.)"* Wait for answer.

### 3. Determine the project directory

Check the lead row for `client_dir_path`:

```
Path exists  → Use that directory (created when lead was added to pipeline)
Path is null  → Create it and store:
                mkdir -p "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<client-slug>"
                update-field <lead-id> '{"client_dir_path": "<path>"}'
```

**All client files go in the client folder.** Do NOT create a separate `reports/projects/` directory.

You'll write three files there:
- `project-brief.md` — internal reference for the freelancer
- `onboarding-checklist.md` — what to collect from the client
- `sitemap.md` — draft IA (skip with note if scope too small)

### 4. Render the brief

Structure is fixed — assemble from lead row + proposal + discovery notes:

```markdown
# Project Brief: <Company Name>

**Client:** <Company>
**Start Date:** <today>
**Target Launch:** <from proposal timeline, else "[To be confirmed]">
**Service Type:** <from tags or discovery>

---

## Client Overview
2–3 paragraphs synthesising lead research + discovery notes.

## Project Goals
What the client wants to achieve, in their own words where possible.

## Scope Summary
Condensed from proposal. Key deliverables, explicit exclusions.

## Key Contacts
- **Primary:** <name, role, email, phone>
- **Technical:** <if different — hosting, domain>
- **Content:** <who provides copy, images>

## Technical Requirements
Hosting, CMS, integrations, third-party services, SSL, domain.

## Content Status
- Copy: provided | pending | needs writing
- Images: provided | pending | needs photography
- Logo: provided | pending | needs design — **NOT generated by the agent**
- Brand guidelines: provided | pending | none exist

## Timeline & Milestones
From proposal timeline, converted to actual dates where possible.

## Notes & Assumptions
Assumptions made, things to verify, risks flagged.

## Links
- Qualification report: <path if exists>
- Proposal: <path if exists>
- Project directory: <client_dir_path>
- Client website: <URL>
```

For any section discovery doesn't cover, write `[To be confirmed]` — never guess.

### 5. Render the onboarding checklist

```bash
python3 -m templates render onboarding-checklists/default.md \
    --json '{"company": "<name>", "service_type": "<type>"}' \
    --out "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<slug>/onboarding-checklist.md"
```

Four sections:

```
📌 Assets to collect     — logo, brand guidelines, colours, fonts, photography, copy
📌 Access & accounts     — domain registrar, hosting, CMS admin, analytics, social
📌 Information needed    — decision makers, communication, competitors, references
📌 Approvals process     — who approves design/content, revision process, turnaround
```

Each item: `Pending` | `Received` | `Not Needed`. Default to `Pending`. Adjust based on discovery notes.

### 6. Generate a draft sitemap

Read proposal scope and discovery notes. Identify content areas. Write to `<client-dir>/sitemap.md`:

```markdown
# Sitemap Draft: <Company>

**Status:** Draft for review with client. Not final.

Home
├── About
│   ├── Our Story
│   └── Team
├── Services
│   ├── <Service 1>
│   └── <Service 2>
├── Portfolio / Work
├── Contact
└── Legal
    ├── Privacy Policy
    └── Terms

For each page:
- **Home:** <purpose, key sections, primary CTA>
- **Services:** <main services, structure, pricing if relevant>

## Open questions
- [Confirm with client: <thing>]
```

**Skip entirely** if single landing page, no useful content structure, or user said they don't need one. Add to brief notes: *"Sitemap skipped: <reason>."*

### 7. Pre-populate tasks

Based on proposal scope, create milestone tasks. Right level of granularity:

```
✅ "Design homepage mockup"        (right — a milestone)
❌ "Create header component"        (too granular)
```

Typical web design project:
```
Kickoff call with client
Collect brand assets (logo, colours, fonts)
Collect content (copy, images)
Design homepage mockup
Client review — design round 1
Build out remaining pages
QA and cross-browser testing
Client review — pre-launch
Launch
```

```bash
python3 -m db_helper task add \
    --lead-id <lead-id> --name "Kickoff call with client" --priority high
```

Auto-logs `task_created` per task.

### 8. Update the lead row

```bash
python3 -m db_helper update-field <lead-id> \
    '{"project_path": "<client_dir_path>"}'

python3 -m db_helper update-status <lead-id> active
```

The first call auto-logs `project_started`. The second logs `status_changed`.

### 9. Optional: welcome email draft

Offer once: *"Want a welcome email draft for the client?"*

If yes, read the project brief first (if not already in context):

```bash
cat "$CLIENT_DIR/project-brief.md"
```

Also read the onboarding checklist for what to reference:

```bash
cat "$CLIENT_DIR/onboarding-checklist.md"
```

Use both files to write a personalised email that references the actual scope and next steps. If files don't exist, fall back to DB fields.

Output **in chat only**:
- Thank them for choosing the freelancer
- Summarise next steps (kickoff call, asset collection, timeline)
- Reference what you need from them (point at the checklist)
- Set communication expectations
- Warm but professional
- **Do not use generic template language** — reference the actual project scope, specific deliverables, and real next steps from the project brief and checklist. Mention their company name, their project, their timeline.

## Edge cases

```
No proposal exists        → Proceed with available context. Flag in brief.
No discovery notes        → Minimal brief with placeholders.
Tasks already exist       → Step 2 handles — ask user.
Single page project       → Shorter brief, minimal checklist, skip sitemap.
Large multi-phase project → Phased onboarding. Phase 1 tasks now, note rest in brief.
Multiple decision makers  → Capture all in Key Contacts. Note final authority.
Existing site, lots of content → "Content migration needed. Audit before sitemap."
```

## What this skill does NOT do

- Generate logos, brand guidelines, design mockups, or any visual creative
- Contact the client directly
- Commit to deadlines or pricing on behalf of the freelancer
- Delete existing tasks (only adds — see Step 2)

## End-of-turn

Tell the user: project directory path, tasks created, status now `active`. Offer the welcome email.

```
"Created $WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/acme-plumbing/ with project-brief.md, onboarding-checklist.md, sitemap.md. Added 9 tasks. Status → active. Want a welcome email draft?"
```

## Notes

- **Format output** for the current channel — adapt formatting to match what the platform supports
- **Cross-skill data contract:**
  - **Reads** from Lead Qualifier: `qualification_report_path`, `research_notes`, `tags`, `client_dir_path`
  - **Reads** from Proposal Builder: `proposal_report_path`, `discovery_notes`, scope details
  - **Writes** for Pipeline Tracker: `project_path`, tasks, status → `active`
- **All client files live in `reports/clients/<slug>/`** — never in a separate `reports/projects/` directory
