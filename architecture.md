# Freelance Forge — Architecture Document

**Version:** 0.2 — Design Phase
**Date:** 2026-04-26
**Author:** Cambrian (design) → Claude Code (implementation)
**Status:** Draft — pending review
**Storage:** See `storage.md` for database schema and local storage specification

---

## 1. Overview

### What It Is

Freelance Forge is a multi-skill bundle that automates the client lifecycle for freelance web designers. One install gives the agent four workflow skills: lead qualification, proposal generation, project onboarding, and pipeline tracking — all connected through a local database.

### Target User

Freelance web designers and small web design studios (1-3 people). They hate admin work, and want to spend more time designing and less time managing leads, writing proposals, and tracking where clients are in the pipeline.

### The Problem

Every freelancer does the same repetitive work: research a lead, score whether they're worth pursuing, write a proposal, set up the project, track where everyone is, remember to follow up. It's not creative work. It's process work. Agents are perfect for process work.

### What Makes This Different

- **Workflow, not tool.** Each sub-skill is independently useful, but together they form a complete pipeline. No other bundle on ClawHub does this.
- **Local-first.** All data stored in a local SQLite database. Zero external dependencies, zero API keys.
- **Agent assists, never replaces.** The human is the designer and the relationship holder. The agent handles the process.
- **Honest about uncertainty.** Every report and assessment explicitly flags what the agent couldn't verify or isn't sure about. Confident wrong answers are worse than honest "I don't know."

---

## 2. Architecture Principles

### 2.1 Local SQLite Database Is the Single Source of Truth

All persistent structured data lives in a local SQLite database (`~/.freelance-forge/pipeline.db`). Full reports live as markdown files alongside the database. When Lead Qualifier finishes, it writes to the database. When Proposal Builder starts, it reads from the database. The database is the communication layer between sub-skills.

**Why:** Zero setup — no API keys, no external services, no authentication. Data is fully portable (single directory). Schema is controlled by us (no discovery or mapping complexity). Reports and metadata live in the same place. Users who want Notion/Sheets can export via CSV/JSON. See `storage.md` for the full specification.

**The agent IS the CRM.** Users never interact with the database directly. They say "show my pipeline" and the agent queries the database and presents the result. They say "update Acme to Active" and the agent updates the database. Whether data lives in Notion or locally, the user experience is identical — but the local approach has zero friction.

### 2.2 Each Sub-Skill Works Standalone

The install script places each sub-skill in a standard skills/ directory. Each has its own SKILL.md with a description that makes it independently discoverable by the skill matcher. A user can install the bundle and only ever use the Lead Qualifier if they want.

**Why:** The skill matcher scans SKILL.md descriptions. If a sub-skill is buried in a nested folder, it won't be triggered when the user says "qualify this lead" three weeks later.

**Database dependency:** Each sub-skill checks for the database on first run. If it doesn't exist, the database helper creates it automatically with default schema. No separate setup step required.

### 2.3 Fixed Schema, Flexible Tags

The database has a fixed schema with defined tables and columns (see `storage.md`). Tags provide flexibility — users can create unlimited custom tags for categorisation (replacing fixed select properties like Budget Range, Service Type, Source). Tags are optional and user-defined.

**Why:** A fixed schema means consistent data, reliable queries, and no mapping complexity. Tags give users the categorisation flexibility that Notion's select properties provided, without the discovery and mapping overhead. The agent suggests tags based on research; users can add, remove, and query tags freely.

### 2.4 Agent Drafts, Human Decides

The agent never sends emails, never creates invoices, never commits to deadlines, never contacts clients directly. It drafts emails for review. It suggests follow-ups. It flags overdue proposals. The human clicks send.

**Why:** Trust boundary. The freelancer's client relationships are their most valuable asset. The agent should support those relationships, not risk them.

### 2.5 Lightweight Assets Only

The agent generates text-based, structured, verifiable assets: project briefs, checklists, sitemaps, email drafts, proposal documents. It does NOT generate logos, brand guidelines, design mockups, or any visual creative work.

**Why:** LLMs are good at structured text. They are not good at visual design. Generating bad creative work is worse than generating none.

### 2.6 Honest About Uncertainty

Every output that involves analysis or assessment must explicitly flag what the agent could not verify, could not test, or is not confident about. This applies to all sub-skills but is most critical for the Lead Qualifier.

**Why:** A confidently wrong assessment is worse than an honest "I couldn't verify this." The freelancer will act on the agent's output. If the agent guesses that a company has a £50K marketing budget when it actually doesn't, that leads to an embarrassing pitch. Flagging uncertainty lets the freelancer verify before acting.

**Pattern:** Every report should include an "Unverified / Could Not Confirm" section that lists:
- Claims that could not be verified from public sources
- Assumptions the agent made (and what those assumptions were based on)
- Things that would require direct conversation with the client to confirm
- Confidence level on key findings (HIGH / MEDIUM / LOW) where appropriate

### 2.7 Reports as Files, Database as Metadata

Each sub-skill generates a **full report or document** as a markdown file in the workspace. The SQLite database stores **summaries and metadata** (scores, one-line recommendations, key dates, statuses), not the full content.

**Why:** A database cell is not the right place for a 500-word qualification brief. The freelancer needs to read a proper document with structure, context, and reasoning. The database is for scanning and querying; files are for reading and acting.

**Pattern:**
- Lead Qualifier → full research brief (file) + score/summary (database)
- Proposal Builder → full proposal document (file) + proposal summary (database)
- Project Onboarder → project brief + checklist + sitemap (files) + project link (database)
- Pipeline Tracker → pipeline digest (chat output) + statuses (database)

**Audit trail:** Every agent action is recorded in the `activity_log` table. "What happened with Acme over the last two weeks?" → one query. This was not possible with external CRM integration and is a key advantage of local storage.

---

## 3. Data Flow

### 3.1 The Client Lifecycle

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌────────────────┐
│   Lead      │     │   Proposal       │     │   Onboarding     │     │   Active       │
│   Qualifier │────▶│   Builder        │────▶│   (Project       │────▶│   Project      │
│             │     │                  │     │    Onboarder)     │     │   + Tracker    │
└─────────────┘     └──────────────────┘     └──────────────────┘     └────────────────┘
     │                      │                        │                        │
     ▼                      ▼                        ▼                        ▼
  SQLite Database — one row per lead, updated at each stage
```

### 3.2 Data Flow Per Stage

**Stage 1: Lead Qualification**
- **Input:** Company name, website URL, or domain
- **Process:** Web research (company site, social, tech stack, site quality)
- **Output:** Qualification score (1-10), research notes, added to database as "Lead"
- **Database writes:** New row in leads table (Company Name, Website, Lead Score, Research Notes, Status = Lead)
- **Activity log:** `lead_created`, `lead_scored`

**Stage 2: Proposal Generation**
- **Input:** Discovery call notes (user provides), pipeline data (read from database)
- **Process:** Combines research + discovery → scoped proposal (deliverables, timeline, pricing)
- **Output:** Proposal document (markdown), pipeline status updated to "Proposal Sent"
- **Database reads:** Lead's row (research notes, score, tags)
- **Database writes:** Proposal Summary, Proposal Date, Status = Proposal Sent
- **Activity log:** `discovery_added`, `proposal_created`, `proposal_sent`

**Stage 3: Project Onboarding**
- **Input:** Client name (from pipeline), confirmed scope
- **Process:** Creates project tasks in database, generates project brief + onboarding checklist + sitemap draft
- **Output:** Project tasks (database), project brief doc, checklist, sitemap
- **Database reads:** Pipeline row for client details
- **Database writes:** New tasks, project_path link, Status = Active
- **Activity log:** `project_started`, `task_created` (for each pre-populated task)

**Stage 4: Pipeline Management**
- **Input:** User requests ("show my pipeline", "update Acme to Active")
- **Process:** Reads database, provides summaries, flags overdue items, updates statuses
- **Output:** Pipeline summary, status updates, follow-up reminders
- **Database reads:** Leads table (filtered queries)
- **Database writes:** Status updates, follow-up dates
- **Activity log:** `status_changed`, `follow_up`

### 3.3 Cross-Stage Data Dependencies

```
Lead Qualifier creates the pipeline row.
    ↓
Proposal Builder reads that row for research context.
    ↓
Project Onboarder reads that row for client details + links the new project DB.
    ↓
Pipeline Tracker monitors all rows for overdue items and status consistency.
```

No sub-skill reads another sub-skill's output files. Everything flows through the database.

**Audit trail:** The `activity_log` table records every action across all stages, giving a complete history per lead.

---

## 4. Local Storage

All persistent data is stored locally. See `storage.md` for the full specification including:
- Database schema (leads, tags, activity_log, tasks tables)
- Directory structure (`~/.freelance-forge/`)
- Config file format
- Database helper module design
- Export functionality (CSV/JSON)
- User querying patterns

### 4.1 Quick Reference

**Database location:** `$FREELANCE_FORGE_CONFIG_DIR/pipeline.db` (default: `~/.freelance-forge/pipeline.db`)
**Config location:** `$FREELANCE_FORGE_CONFIG_DIR/config.json`
**Reports directory:** `$FREELANCE_FORGE_CONFIG_DIR/reports/`
**No API keys required. No external dependencies.**

### 4.2 Schema Summary

Four tables: `leads` (pipeline), `tags` + `lead_tags` (flexible categorisation), `activity_log` (audit trail), `tasks` (per-client project tasks). Full schema with all columns, types, and indexes in `storage.md` §3.

### 4.3 Tags Replace Fixed Properties

Budget Range, Service Type, Source — all replaced by a tags system. Tags are user-defined with optional categories. The agent suggests tags based on research; users can add/remove/query tags freely.

### 4.4 Activity Log

Every agent action is recorded. Enables queries like "what happened with Acme?" or "how many leads did I qualify this month?" This was not possible with external CRM integration.

### 4.5 Export

One-way export to CSV (for spreadsheet import) and JSON (for backup/programmatic use). No sync, no two-way updates. Users who want Notion/Sheets can export and import.

### 4.6 First-Run Setup

On first run, the database helper creates `pipeline.db` with all tables, indexes, and default config. No user interaction required. Setup is instant — one database file, zero configuration.

---

## 5. Sub-Skill Architecture

### 5.1 Lead Qualifier

**Trigger phrases:** "qualify this lead", "research this company", "score this prospect"

**Input:** Company name, website URL, or domain

**Process:**
1. Research the company: website content, tech stack (if detectable), social presence, industry
2. Assess fit: do they need web design services? Are they the right size? Is there budget signal?
3. Score 1-10 with brief reasoning
4. Write to database (new lead row with research notes)
5. Offer to draft a qualification summary or follow-up email

**Output:**
- Full qualification report (markdown file) — see report structure below
- Qualification score + reasoning (displayed to user and stored in database)
- New database row (summary data only)
- Optional: draft follow-up email (chat output, user copies and sends)

**Qualification Report Structure:**
```
# Lead Qualification: [Company Name]

## Company Overview
[Full research summary — what the company does, size, location, industry]

## Fit Assessment
**Score: X/10**
- [Reasoning for score — why this score, what supports it]

## Key Findings
- [Finding 1 — e.g., current site is outdated]
- [Finding 2 — e.g., spending on ads but poor landing page]
- [Finding 3 — e.g., no mobile optimisation]

## Unverified / Could Not Confirm ⚠️
- [Thing that couldn't be verified — e.g., "Could not confirm budget. No pricing or budget information found on public sources."]
- [Assumption made — e.g., "Assuming 5-10 employees based on LinkedIn, but company size page not accessible."]
- [Requires client conversation — e.g., "Decision-making process unknown — unclear if marketing manager or owner makes website decisions."]

## Recommendation
[What the freelancer should do with this lead, based on available information]

## Suggested Next Steps
[Numbered action items for the freelancer]
```

**Critical:** The "Unverified / Could Not Confirm" section is non-negotiable. Every qualification report must include it. If the agent is highly confident about everything (rare), the section says "All findings verified from public sources" rather than being omitted.

**Database interaction:**
- Creates new row in leads table
- Writes: Company Name, Website, Lead Score, Research Quality, Research Notes (summary only, not full report), Status = Lead
- Suggests tags based on research (e.g., "wordpress", "local-business")
- Logs: `lead_created`, `lead_scored` in activity_log

**Edge cases:**
- Very little web presence → flag as "limited info, manual research recommended" with specific note on what couldn't be found
- Company is clearly too small/large for freelancer scope → note in score reasoning
- Already exists in pipeline → alert user, offer to update existing row instead
- Multiple companies with similar names → flag ambiguity, ask user to confirm which one

---

### 5.2 Proposal Builder

**Trigger phrases:** "build a proposal", "write a proposal for", "create proposal from discovery"

**Input:** Client name (to look up in pipeline) + discovery call notes (user pastes or references a file)

**Process:**
1. Read the client's database row for context (research notes, lead score, tags)
2. Combine pipeline data + discovery notes
3. Generate scoped proposal:
   - Executive summary (why this project, what problem we're solving)
   - Scope of work (specific deliverables, what's included, what's not)
   - Timeline (phases, milestones, estimated dates)
   - Pricing (broken down by deliverable or phase)
   - Terms (revisions, payment schedule, assumptions)
4. Save proposal as markdown file
5. Update database: Proposal Summary, Proposal Date, Status = Proposal Sent

**Output:**
- Full proposal document (markdown file)
- Database row updated (summary and status)
- Optional: draft email with proposal summary (chat output, user copies and sends)

**Database interaction:**
- Reads: client's row (research notes, lead score, tags)
- Writes: Proposal Summary (brief, not full proposal), Proposal Date, Status
- Logs: `discovery_added`, `proposal_created`, `proposal_sent` in activity_log

**Edge cases:**
- No discovery notes provided → prompt user to provide them, offer to generate a discovery template
- No pipeline row for this client → suggest running Lead Qualifier first, or create a minimal row
- Pricing: agent should present ranges based on service type and scope, not exact figures. The freelancer sets the final price.
- Insufficient information for a section → flag it in the proposal: "[Confirm with client: technical requirements for booking system]"

---

### 5.3 Project Onboarder

**Trigger phrases:** "set up project for", "onboard this client", "start project"

**Input:** Client name (from pipeline)

**Process:**
1. Read the client's database row for project details
2. Create project tasks in the database for this client
3. Generate project brief:
   - Client overview
   - Project scope (from proposal/discovery)
   - Key contacts
   - Timeline and milestones
   - Technical requirements (hosting, CMS, integrations)
4. Generate onboarding checklist:
   - Assets needed (logos, brand guidelines, content, photos, hosting access, domain access)
   - Accounts to set up (hosting, CMS, analytics, email)
   - Stakeholder contacts
   - Preferences (color preferences, reference sites, competitor sites)
5. Generate sitemap/IA draft from discovery notes
6. Set project_path in database, update Status = Active

**Output:**
- Project tasks (database rows, linked to lead)
- Project brief (markdown file)
- Onboarding checklist (markdown file)
- Sitemap/IA draft (markdown file)
- Optional: draft welcome email with checklist (chat output, user copies and sends)

**Database interaction:**
- Reads: client's row
- Creates: task rows in tasks table
- Writes: updates row with project_path and status
- Logs: `project_started`, `task_created` (for each task) in activity_log

**Edge cases:**
- Pipeline row missing proposal data → use whatever's available, flag gaps
- Tasks already exist for this lead → ask if user wants to add to existing or start fresh
- Very large project → suggest phased onboarding (brief first, detailed sitemap later)
- Missing discovery notes → generate onboarding checklist with placeholders marked for confirmation

---

### 5.4 Pipeline Tracker

**Trigger phrases:** "show my pipeline", "pipeline update", "update [client] to [status]", "any overdue follow-ups"

**Input:** Various — status updates, pipeline queries, follow-up requests

**Process:**
1. **Pipeline summary:** Query all leads, group by status, present as a digest
2. **Status update:** Change a specific client's status
3. **Follow-up check:** Compare Proposal Date / Last Follow-Up to current date, flag items overdue by configured threshold (default 5 days)
4. **Follow-up draft:** For overdue items, offer to draft a follow-up email using the client's data
5. **Tag management:** Add, remove, and query tags
6. **Follow-up suggestions:** Check `status_since` against per-status thresholds, flag stale leads
7. **History:** Show activity log for a specific lead or time range
8. **Task management:** View, update, and add tasks for active projects
9. **Export:** Export pipeline to CSV or JSON

**Output:**
- Pipeline digest (grouped by status, with follow-up suggestions)
- Status updates written to database
- Stale lead alerts ("follow up suggested — 5 days in lead")
- Tag queries and updates
- Activity history
- Task lists and updates
- Export files (CSV/JSON)
- Optional: draft follow-up emails

**Database interaction:**
- Reads: leads table (filtered queries), activity_log, tags, tasks
- Writes: status updates, follow-up dates, tag associations, task updates
- No separate setup required — database is created automatically on first use

**Edge cases:**
- Empty pipeline → "No leads in pipeline. Run Lead Qualifier to add your first lead."
- Many stale items → prioritize by lead score
- Status inconsistency (e.g., "Active" but no tasks) → flag to user
- Agent mentions follow-up suggestions once per session, doesn't repeat

---

## 6. Shared Components

These are utilities referenced by multiple sub-skills, not sub-skills themselves.

### 6.1 Database Helper

A Python module (`scripts/db_helper.py`) that handles all SQLite interactions. See `storage.md` §5 for full design.

Key functions:
- Database and table creation (first-run, automatic)
- Connection management (context manager pattern)
- CRUD operations for leads, tags, tasks, activity_log
- Query helpers: filter by status, find stale leads, search by name, tag queries, task queries
- Follow-up suggestion system (per-status thresholds via `status_since`)
- Export to CSV/JSON
- Config file read/write
- Path resolution (env var with default)
- Dry-run mode for write operations

### 6.2 Web Research Helper

Used by Lead Qualifier:
- Fetch and parse a company's website
- Extract basic info (company description, services, contact info)
- Detect tech stack indicators (CMS, hosting, frameworks)
- Find social media profiles
- **Track what couldn't be found** — return a structured list of unverified claims alongside verified findings

### 6.3 Config Manager

Used by all sub-skills. Merged into the database helper module — config is loaded and validated as part of database initialisation.
- Load config from `$FREELANCE_FORGE_CONFIG_DIR/config.json` (env var with default `~/.freelance-forge/`)
- Create with defaults if missing
- Provide sensible defaults for missing optional fields
- Support cross-platform paths via env vars

### 6.4 Template System

Used by Proposal Builder and Project Onboarder:
- Read template markdown files from `references/`
- Inject dynamic data (company name, dates, scope details)
- Output completed documents

Templates are starting points, not rigid forms. The agent should adapt content based on the specific client context, not fill in blanks mechanically.

### 6.5 Report Generator

Used by all sub-skills:
- Generate markdown report files with consistent structure
- Include uncertainty sections in every analytical output
- Save to `$FREELANCE_FORGE_CONFIG_DIR/reports/` (subdirectories for qualifications, proposals, projects)
- Return the file path so the agent can reference it in chat

---

## 7. Bundle Structure

### 7.1 File Layout

```
freelance-forge/
├── openclaw.bundle.json          # Bundle manifest
├── openclaw-install.sh           # Install script
├── README.md                     # User-facing documentation
│
├── skills/
│   ├── lead-qualifier/
│   │   └── SKILL.md              # Lead qualification skill
│   ├── proposal-builder/
│   │   └── SKILL.md              # Proposal generation skill
│   ├── project-onboarder/
│   │   └── SKILL.md              # Project onboarding skill
│   └── pipeline-tracker/
│       └── SKILL.md              # Pipeline management skill
│
├── scripts/
│   ├── db_helper.py             # SQLite database helper module
│   ├── web_research.py          # Web research helper
│   └── templates.py             # Template rendering
│
└── references/
    ├── proposal-templates/
    │   └── default.md            # Default proposal template
    ├── email-drafts/
    │   ├── welcome.md            # Client welcome draft
    │   ├── asset-request.md      # Asset request draft
    │   ├── follow-up-proposal.md # Proposal follow-up draft
    │   └── project-kickoff.md    # Project kickoff draft
    └── onboarding-checklists/
        └── default.md            # Standard onboarding checklist
```

### 7.2 Bundle Manifest

```json
{
  "name": "freelance-forge",
  "displayName": "Freelance Forge — Lead to Launch",
  "version": "1.0.0",
  "description": "Complete freelance web designer toolkit — qualify leads, generate proposals, onboard clients, and track your pipeline. Zero setup, runs locally.",
  "type": "bundle",
  "bundle": {
    "format": "skill-collection",
    "skills": [
      {
        "name": "lead-qualifier",
        "path": "skills/lead-qualifier/SKILL.md",
        "description": "Research and score prospective clients"
      },
      {
        "name": "proposal-builder",
        "path": "skills/proposal-builder/SKILL.md",
        "description": "Generate scoped proposals from discovery notes"
      },
      {
        "name": "project-onboarder",
        "path": "skills/project-onboarder/SKILL.md",
        "description": "Set up projects, briefs, and checklists"
      },
      {
        "name": "pipeline-tracker",
        "path": "skills/pipeline-tracker/SKILL.md",
        "description": "Pipeline management and follow-up tracking"
      }
    ],
    "scripts": [
      "scripts/db_helper.py",
      "scripts/web_research.py",
      "scripts/templates.py"
    ]
  },
  "install": {
    "script": "openclaw-install.sh"
  }
}
```

### 7.3 Install Script Behavior

The `openclaw-install.sh` script should:

1. Copy each sub-skill's SKILL.md to the user's skills directory (standalone, discoverable)
2. Copy shared scripts to a `freelance-forge/` directory within the skills folder
3. Copy reference files (templates, checklists) alongside the scripts
4. Create `~/.freelance-forge/` directory and subdirectories if they don't exist
5. Print a brief welcome message explaining what was installed and how to get started
6. Do NOT create the database — that happens automatically on first use of any sub-skill
7. Do NOT ask for credentials — no credentials are required

---

## 8. Design Decisions

### Why Local SQLite Over External CRM
- Zero setup — no API keys, no integrations, no auth flows, no paywalls
- No dependency on third-party service reliability or pricing changes
- Data is fully portable — single directory the user owns and can back up
- Schema is controlled by us — consistent data, reliable queries, no mapping complexity
- Reports and metadata in one place — coherent audit trail
- Users who want Notion/Sheets can export via CSV/JSON — one-way, no sync
- The agent IS the query interface — users never interact with the database directly

### Why Drafts, Not Sends
- Client relationships are the freelancer's most valuable asset
- An agent sending an email to the wrong person, with wrong info, or at the wrong time could damage a relationship permanently
- Drafting is valuable (saves time writing) without the risk of sending

### Why Each Sub-Skill Standalone
- The skill matcher can only find skills in the standard skills/ directory
- Nested sub-skills would be invisible to the agent after the bundle is installed
- Users should be able to use just one piece if that's all they need

### Why No Invoice Generation (v1)
- Invoices involve money. Getting them wrong has real consequences.
- Requires payment API integration (Stripe, Xero, GoCardless) which is a separate scope.
- The pipeline tracker shows where clients are — the freelancer can generate invoices themselves using the pipeline data as reference.

### Why No Automated Scheduling
- Automated follow-up reminders are fine ("flag overdue items"). Automated actions (send email after 5 days) cross the trust boundary.
- The agent should inform and suggest, never act autonomously on client communication.

### Why Fixed Schema with Flexible Tags
- A fixed schema means consistent data, reliable queries, no mapping complexity
- Tags provide unlimited user-defined categorisation — no predefined categories, no schema changes
- The agent suggests tags based on research; users add/remove/query freely
- No external service dependency — works offline, no API limits, no paywalls

---

## 9. Constraints & Boundaries

### The Agent Must Never
- Send emails or messages to clients (see §2.4 — drafting is chat output only)
- Generate or modify invoices or financial documents
- Commit to deadlines, pricing, or scope on behalf of the freelancer
- Access client accounts (hosting, email) directly
- Delete lead rows from the database (status can be changed to "lost" but data is preserved)
- Share client information across different leads/clients
- Present uncertain findings as confirmed facts (see §2.6)
- Omit the uncertainty section from any analytical report

### What Requires User Confirmation
- **Changing a lead's status to "Lost"** — significant signal that should not happen by accident. Data is preserved and status can be reverted, but the confirmation prevents accidental changes.
- Exporting pipeline data

### Scope Boundaries
- Single freelancer / small studio (1-3 people), not enterprise
- Web design projects only (not general freelancing, not app development)
- Local storage only in v1 (no cloud sync, no external CRM integration)
- English language only (v1)

---

## 10. Implementation Notes for Claude Code

### General Guidance
- Each SKILL.md should be self-contained — it should work if installed alone, without the other sub-skills present
- Shared scripts should handle graceful degradation (if database doesn't exist, create it; if config is missing, use defaults)
- Keep database queries efficient — fetch what's needed, don't pull entire tables when a filtered query works
- All user-facing output should be concise and actionable — freelancers are busy, they want the answer, not a wall of text
- Error handling should suggest the fix, not just report the error ("Database not found at ~/.freelance-forge/pipeline.db. It will be created automatically on first use.")
- Every analytical output must include uncertainty flags — what the agent couldn't verify, what assumptions were made, what requires human confirmation (see §2.6)
- Full reports are saved as files; database stores summaries and metadata only (see §2.7)
- Email drafting means outputting text in the chat for the user to copy and send — no inbox integration, no email API, no OAuth
- Every agent action that modifies the database must also write to the activity_log — this is non-negotiable
- The web research script should return source-annotated raw data (`{claim, source, url, confidence}`), not pre-summarised findings
- The database helper needs a `dry_run` option on write operations — useful for first-time setup and user confidence

### What Claude Code Has Freedom On
- Exact SKILL.md structure and wording (follow the SKILL.md standard, but the specific sections and phrasing are up to you)
- Script implementation details (language, libraries, error handling approach)
- Template content and structure
- How to present pipeline summaries and digests
- How to handle edge cases not explicitly listed above
- How to implement web fetching and parsing (library choices, error handling)
- The specific format of database summaries
- File naming conventions for reports

### What Should Stay Fixed
- The four sub-skills and their responsibilities (§5)
- Local SQLite database as the single source of truth (§2.1)
- Database schema (see `storage.md` §3)
- Tags system replacing fixed select properties (§4.3)
- Activity log recording every agent action (§4.4)
- Draft-only email policy — chat output, no inbox integration (§2.4)
- Honest uncertainty flagging in every analytical report (§2.6)
- Reports as files, database as metadata (§2.7)
- Cross-agent compatibility via env vars (only `FREELANCE_FORGE_CONFIG_DIR`)
- The constraints and boundaries (§9)
- The config file structure (see `storage.md` §4)
- Each sub-skill working standalone after install
- Export to CSV/JSON for data portability (§4.5)

---

## 11. Future Considerations (v2+)

- **Xero/Stripe invoice generation** — read pipeline data, generate invoices in accounting software
- **Calendar integration** — detect discovery call scheduling, deadline tracking
- **Cloud sync** — optional sync to Notion, Google Sheets, or cloud storage for multi-device access
- **Automated follow-up sequences** — configurable, user-approved sequences (not autonomous)
- **Portfolio case study generator** — after project completion, generate a case study from project data
- **Retention/upsell suggestions** — based on completed project history, suggest relevant additional services
- **Notion/CRM import** — one-time import from existing Notion pipeline or other CRM
- **Multi-language support**
- **Agency-scale** — multiple team members, role-based views, assignment tracking
