---
name: project-onboarder
description: Turn a signed proposal into a running project. Use when the user says a client signed, accepted, or is ready to start. Creates project tasks in the database, generates a project brief, an onboarding checklist, and a draft sitemap, then sets the lead's status to active.
---

# Project Onboarder

Take a client whose proposal was accepted and produce the four things needed to run the project: a brief, a checklist, a draft sitemap, and the initial set of tasks. This is the bridge between "sold" and "building."

## When to use this skill

Trigger phrases:
- "set up project for <client>"
- "onboard <client>"
- "start project for <client>"
- "create project for <client>"
- "<client> signed the proposal"
- "they said yes" (when a recent proposal exists)
- "we're good to go with <client>"

## Tools

```bash
SHARED="${FREELANCE_FORGE_CONFIG_DIR:-$HOME/.freelance-forge}/shared"
PYTHONPATH="$SHARED" python3 -m db_helper <command>
PYTHONPATH="$SHARED" python3 -m templates render <path> --json '...'
```


## First Run Check

Before the flow below, run the guard clause:
```bash
python3 -c "import sys; sys.path.insert(0, '$HOME/.freelance-forge/shared'); import db_helper" 2>/dev/null && echo OK
```

If `OK` — proceed to Flow.

If it fails — read `~/.freelance-forge/references/setup.md` and execute the setup steps. Once setup completes, return here and proceed with the Flow.


## Flow

### 1. Find the lead

```
python3 -m db_helper get-lead --company "<client>"
```

Disambiguate fuzzy matches with the user. Once you have the lead row, also fetch tags and any earlier qualification/proposal files:

```
python3 -m db_helper tag list --lead-id <lead-id>
```

Look in `$FREELANCE_FORGE_CONFIG_DIR/reports/qualifications/` and `reports/proposals/` for related markdown files. Read them for context.

### 2. Check for existing tasks

```
python3 -m db_helper task list --lead-id <lead-id>
```

If tasks already exist, ask: *"This client has 4 existing tasks. Add the new onboarding tasks to the existing set, or do you want to start fresh? (Starting fresh leaves the old tasks but adds the new ones — I won't delete anything.)"* Wait for the answer.

### 3. Build the project directory

Create `$FREELANCE_FORGE_CONFIG_DIR/reports/projects/<client-slug>/` (slug = lowercased company, non-alphanumeric replaced with `-`).

You'll write three files there:
- `project-brief.md` — internal reference for the freelancer
- `onboarding-checklist.md` — what to collect from the client
- `sitemap.md` — draft IA (skip with note if scope too small or content unclear)

### 4. Render the brief

The brief follows the structure in `project-onboarder.md` §5. You can render it directly or assemble from the lead row + proposal — either way, the structure is fixed:

```markdown
# Project Brief: <Company Name>

**Client:** <Company>
**Start Date:** <today>
**Target Launch:** <from proposal timeline if specified, else "[To be confirmed]">
**Service Type:** <from tags or discovery>

---

## Client Overview
2–3 paragraphs synthesising lead research + discovery notes.

## Project Goals
What the client wants to achieve, in their own words where possible. Pull from discovery notes.

## Scope Summary
Condensed from proposal. Key deliverables, explicit exclusions.

## Key Contacts
- **Primary:** <name, role, email, phone — from discovery or pipeline>
- **Technical:** <if different — hosting, domain access>
- **Content:** <who provides copy, images>

## Technical Requirements
Hosting, CMS, integrations, third-party services, SSL, domain. Pull from discovery + proposal.

## Content Status
- Copy: provided | pending | needs writing
- Images: provided | pending | needs photography
- Logo: provided | pending | needs design — **flag: this is NOT something the agent generates**
- Brand guidelines: provided | pending | none exist

## Timeline & Milestones
From proposal timeline, converted to actual dates where possible.

## Notes & Assumptions
Any assumptions made, things to verify, risks flagged during discovery.

## Links
- Qualification report: <path if exists>
- Proposal: <path if exists>
- Project directory: <path to reports/projects/<slug>/>
- Client website: <URL>
```

For any section discovery doesn't cover, write `[To be confirmed]` — never guess.

### 5. Render the onboarding checklist

Use the template:
```
python3 -m templates render onboarding-checklists/default.md \
    --json '{"company": "<name>", "service_type": "<type>"}' \
    --out "$FREELANCE_FORGE_CONFIG_DIR/reports/projects/<slug>/onboarding-checklist.md"
```

The checklist has four sections (project-onboarder.md §6):
- **Assets to collect** — logo, brand guidelines, colours, fonts, photography, copy, marketing materials
- **Access & accounts** — domain registrar, hosting, CMS admin, analytics, social, email
- **Information needed** — decision makers, communication preferences, competitor sites, references, deadlines
- **Approvals process** — who approves design, who approves content, how revisions submitted, expected turnaround

Each item carries a status marker: `Pending` | `Received` | `Not Needed`. Default everything to `Pending`. Adjust based on what discovery notes already covered (e.g. if they mentioned WordPress, mark "CMS admin access" as Pending and add a note).

### 6. Generate a draft sitemap

Read the proposal scope and discovery notes. Identify main content areas. Propose a page hierarchy.

Write to `<project-dir>/sitemap.md`:

```markdown
# Sitemap Draft: <Company>

**Status:** Draft for review with client. Not final.

```
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
```

For each page:
- **Home:** <purpose, key sections, primary CTA>
- **Services:** <main services, structure, pricing if relevant>
- ...

## Open questions
- [Confirm with client: <thing>]
```

**Skip the sitemap entirely** if:
- Project is a single landing page
- Discovery notes give no useful content structure
- The user explicitly said they don't need one

If skipping, add a line to the project brief's "Notes & Assumptions" section: *"Sitemap skipped: <reason>."*

### 7. Pre-populate tasks

Based on the proposal scope, create high-level milestone tasks. Don't over-specify ("Create header component" is too granular; "Design homepage mockup" is right).

Examples for a typical web design project:
- "Kickoff call with client"
- "Collect brand assets (logo, colours, fonts)"
- "Collect content (copy, images)"
- "Design homepage mockup"
- "Client review — design round 1"
- "Build out remaining pages"
- "QA and cross-browser testing"
- "Client review — pre-launch"
- "Launch"

Add each one:
```
python3 -m db_helper task add \
    --lead-id <lead-id> --name "Kickoff call with client" --priority high
```

The shim auto-logs `task_created` per task.

### 8. Update the lead row

```
python3 -m db_helper update-field <lead-id> \
    '{"project_path": "<path to reports/projects/<slug>/>"}'

python3 -m db_helper update-status <lead-id> active
```

The first call auto-logs `project_started` (because `update-field` infers `project_started` when `project_path` is set). The second logs `status_changed`.

### 9. Optional: welcome / kickoff email draft

Offer once: *"Want a welcome email draft for the client?"*

Rules (project-onboarder.md §10):
- Thank them for choosing the freelancer
- Summarise next steps (kickoff call, asset collection, timeline)
- Reference what you need from them (point at the checklist)
- Set communication expectations (how often, via what channel)
- Warm but professional — sets the tone

Output **in chat only**.

## Edge cases

| Scenario | Approach |
|---|---|
| No proposal exists | Proceed with available context. Flag in the brief: "No formal proposal found. Brief built from lead research + user input." |
| No discovery notes anywhere | Minimal brief with placeholders. Freelancer fills in during kickoff call. |
| Tasks already exist | Step 2 handled — ask the user. |
| Very small project (single page) | Shorter brief, minimal checklist, skip sitemap. |
| Very large multi-phase project | Suggest phased onboarding. Create Phase 1 tasks now, note remaining phases in the brief. |
| Multiple decision makers | Capture all in Key Contacts. Note who has final authority if mentioned. |
| Existing site with lots of content | Add to brief: "Content migration needed from existing site. Audit before finalising sitemap." |

## What this skill does NOT do

- Does not generate logos, brand guidelines, design mockups, or any visual creative work (architecture §2.5)
- Does not contact the client directly (architecture §2.4)
- Does not commit to deadlines or pricing on behalf of the freelancer
- Does not delete existing tasks (only adds — see step 2)

## End-of-turn

Tell the user: project directory path, number of tasks created, lead status now `active`. Offer the optional welcome email.

Example:
> Created `~/.freelance-forge/reports/projects/acme-plumbing/` with project-brief.md, onboarding-checklist.md, sitemap.md. Added 9 tasks. Lead status updated to `active`. Want a welcome email draft for the client?
