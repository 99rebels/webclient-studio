# Sub-Skill Deep Dive: Project Onboarder

**Parent:** Freelance Forge — `architecture.md`
**Version:** 0.2 — Design Phase (updated for local SQLite storage)
**Date:** 2026-04-26

---

## 1. Purpose

The Project Onboarder turns a signed proposal into a running project. When the client says yes, this sub-skill creates project tasks in the database, generates a structured project brief, builds an onboarding checklist, and drafts an initial sitemap. It's the bridge between "sold" and "building."

**It does four things:**
1. **Create project tasks** — create tasks in the database for the client's project
2. **Generate a project brief** — a structured document capturing scope, contacts, timeline, and technical requirements
3. **Build an onboarding checklist** — what the freelancer needs from the client before work can begin
4. **Draft a sitemap/IA** — initial information architecture based on discovery notes and proposal scope

---

## 2. When It Triggers

**Primary triggers:**
- "set up project for [client]"
- "onboard [client]"
- "start project for [client]"
- "create project for [client]"
- "[client] signed the proposal"

**Context triggers:**
- "they said yes" (if a recent proposal exists in the pipeline)
- "we're good to go with [client]"

---

## 3. Input

**Required:**
- Client name — matching a row in the pipeline database

**Read from database:**
- The client's full lead row (research notes, discovery notes, proposal summary, tags)
- Proposal file if it exists (from `$FREELANCE_FORGE_CONFIG_DIR/reports/proposals/`)

**Read from workspace (if available):**
- Qualification report (from Lead Qualifier)
- Any other files the freelancer has created for this client

The onboarder should use all available context. If some files are missing (e.g., no qualification report because the freelancer skipped the Lead Qualifier), proceed with what's available and flag the gaps in the project brief.

---

## 4. Project Tasks

### Creating Tasks

Create task rows in the database's `tasks` table for this client's project. Use the default task schema from `storage.md` §3.4.

**Default task properties:**
- Task Name (text)
- Status (select: todo, in_progress, done)
- Priority (select: high, medium, low)
- Due Date (date)
- Notes (text)
- Is Deliverable (boolean)

**Customisation:** If the proposal mentions specific phases (e.g., "Phase 1: Discovery, Phase 2: Design, Phase 3: Build"), suggest creating matching status options or task groups. The user confirms.

### Linking to Lead

After creating tasks, update the lead's `project_path` field to point to the project directory. Update the lead's status to "active".

If tasks already exist for this lead, ask whether to add to existing or start fresh.

### Pre-populating Tasks

Based on the proposal scope, generate initial tasks. These should be high-level milestones, not granular task breakdowns:

- "Kickoff call with client"
- "Collect brand assets (logo, colours, fonts)"
- "Collect content (copy, images, photos)"
- "Design homepage mockup"
- "Client review — design round 1"
- etc.

The exact tasks depend on the proposal scope. Don't over-specify — these are starting points the freelancer will refine.

Log: `project_started` + `task_created` for each task in activity_log.

---

## 5. Project Brief

A structured document that captures everything the freelancer needs to execute the project. It's an internal reference, not client-facing.

### Structure

```markdown
# Project Brief: [Company Name]

**Client:** [Company Name]
**Start Date:** [today]
**Target Launch:** [from proposal timeline, if specified]
**Service Type:** [from pipeline: Website Redesign / New Website / etc.]

---

## Client Overview
[2-3 paragraphs synthesising the lead research and discovery notes. Who they are, what they do, why they came to us.]

## Project Goals
[What the client wants to achieve, in their own words where possible. Pull from discovery notes.]

## Scope Summary
[Condensed version of the proposal's scope section. Key deliverables, explicit exclusions.]

## Key Contacts
- **Primary:** [name, role, email, phone — from discovery notes or pipeline]
- **Technical:** [if different — who has hosting access, domain access, etc.]
- **Content:** [who's providing copy, images, etc.]

## Technical Requirements
[Hosting, CMS, integrations, third-party services, SSL, domain management. Pull from discovery notes and proposal.]

## Content Status
- Copy: [provided / pending / needs writing]
- Images: [provided / pending / needs photography]
- Logo: [provided / pending / needs design — flag: this is NOT something the agent generates]
- Brand guidelines: [provided / pending / none exist]

## Timeline & Milestones
[From proposal timeline, converted to actual dates where possible.]

## Notes & Assumptions
[Any assumptions made, things to verify, risks flagged during discovery.]

## Links
- Qualification report: [path if exists]
- Proposal: [path if exists]
- Project directory: [path to reports/projects/<slug>/]
- Client website: [URL]
```

**Missing information:** If the discovery notes don't cover a section, mark it as "[To be confirmed]" rather than leaving it blank or guessing. The freelancer fills these in as they learn more.

---

## 6. Onboarding Checklist

A practical list of what the freelancer needs from the client before work can begin. This is the freelancer's internal tracking tool — it's not sent to the client directly (though an email draft can be generated from it).

### Checklist Categories

**Assets to Collect:**
- Logo files (vector format if possible — SVG, AI, EPS)
- Brand guidelines / style guide (if exists)
- Brand colours (hex codes)
- Fonts / typography preferences
- Photography (professional shots, stock images, client-supplied)
- Copy / text content for each page
- Any existing marketing materials (brochures, business cards, ads)

**Access & Accounts:**
- Domain registrar login
- Current hosting account (if exists)
- CMS admin access (if exists)
- Google Analytics / Search Console access
- Social media account access (if relevant to project)
- Email hosting details (if email setup is in scope)

**Information Needed:**
- Decision maker(s) and their availability
- Preferred communication method and frequency
- Competitor sites they like/dislike (and why)
- Reference sites for design inspiration
- Any deadlines or external dependencies (events, launches, campaigns)

**Approvals Process:**
- Who approves design work?
- Who approves content?
- How should revisions be submitted? (email, shared document)
- Expected turnaround time for client reviews

### Output

The checklist should be a markdown file that the freelancer can tick off as items are received. Each item should have a status: Pending / Received / Not Needed.

---

## 7. Sitemap / Information Architecture

### What It Is

A draft sitemap showing the proposed page structure and navigation hierarchy for the website. This is based on the discovery notes and proposal scope — it's a starting point for the freelancer to discuss with the client, not a final plan.

### How to Generate It

1. Read the proposal scope and discovery notes
2. Identify the main content areas and user needs
3. Propose a page hierarchy:

```
Home
├── About
│   ├── Our Story
│   └── Team
├── Services
│   ├── Service A
│   ├── Service B
│   └── Service C
├── Portfolio / Work
├── Blog (optional)
├── Contact
└── Legal
    ├── Privacy Policy
    └── Terms
```

4. For each page, include a brief note on purpose and key content:
   - **Home:** Hero section, services overview, testimonials CTA, call-to-action
   - **Services:** Main services with descriptions, pricing table (if applicable)
   - **Contact:** Form, phone, email, map, business hours

### What It's Not

- It's not a wireframe or design
- It's not final — the freelancer reviews and adjusts before presenting to the client
- It doesn't include technical implementation details
- It's based on available information; gaps should be flagged

### When to Skip It

- If the project is too small for a formal sitemap (e.g., a single landing page)
- If the discovery notes provide no useful information about content structure
- If the freelancer explicitly says they don't need it

In these cases, note in the project brief that a sitemap was skipped and why.

---

## 8. Database Interaction

### Prerequisite Check
The database helper handles this automatically — if the database doesn't exist, it's created.

### Reading
- Fetch the client's lead row
- Read all available fields for context

### Writing
- Insert task rows into the tasks table
- Update lead row with project_path and status
- Log: `project_started`, `task_created` (for each task) in activity_log

### If No Proposal Exists
The onboarder should still work. It'll have less context (only the lead research and whatever the freelancer provides), but it can generate a basic project brief and checklist. Flag the missing proposal in the brief.

---

## 9. Output Files

All saved to `$FREELANCE_FORGE_CONFIG_DIR/reports/projects/[client-name]/`:

| File | Purpose |
|---|---|
| `project-brief.md` | Internal reference for the freelancer |
| `onboarding-checklist.md` | Track what's needed from the client |
| `sitemap.md` | Draft page structure for client review |

Plus task rows in the database (linked to lead via `lead_id`).

---

## 10. Optional: Welcome Email Draft

After onboarding, offer to draft a welcome/kickoff email for the client. This is chat output only — the user copies and sends.

The email should:
- Thank them for choosing the freelancer
- Summarise next steps (kickoff call, asset collection, timeline)
- Reference the onboarding checklist (what the freelancer needs from them)
- Set expectations for communication (how often, via what channel)
- Be warm but professional — this sets the tone for the working relationship

---

## 11. Edge Cases

| Scenario | Approach |
|---|---|
| No proposal in pipeline | Proceed with available context. Flag in the brief that no formal proposal was found. |
| No discovery notes anywhere | Build a minimal brief with placeholders. The freelancer fills in details during the kickoff call. |
| Client already has a project database | Ask: use existing or create new? Don't duplicate. |
| Very small project (single page) | Simplify — brief can be shorter, checklist can be minimal, sitemap might be unnecessary. |
| Very large project (multi-phase) | Suggest phased onboarding. Create the Phase 1 project first, add phases as they begin. Note remaining phases in the brief. |
| Multiple decision makers mentioned | Capture all of them in the Key Contacts section with roles. Note who has final authority if mentioned. |
| Client has existing website with lots of content | Flag in the brief: "Content migration needed from existing site. Audit existing pages before finalising sitemap." |

---

## 12. Design Decisions

### Why Tasks Live in a Shared Table Keyed by `lead_id`
A single `tasks` table with a `lead_id` foreign key is simpler and more flexible than per-client databases. It enables cross-client queries ("show me all overdue tasks across all projects"), requires no per-client schema management, and keeps data consistent through cascading deletes. The Project Onboarder creates the initial task set; the Pipeline Tracker manages them day-to-day.

### Why the Project Brief Is Internal-Only
The brief contains honest assessments (lead score, research notes, assumptions). These are useful for the freelancer but shouldn't be client-facing. The proposal is the client-facing document.

### Why the Sitemap Is a Draft, Not a Final Plan
The freelancer knows their client and their design process better than the agent does. The sitemap is a thinking tool — a structured starting point that the freelancer reviews, adjusts, and potentially presents to the client. It saves 30 minutes of staring at a blank page, but the freelancer makes the final call.

### Why the Checklist Tracks Receipt Status
"Did the client send the logo?" is a question freelancers ask themselves repeatedly. A checklist with Pending/Received/Not Needed status means the freelancer can check at a glance instead of digging through emails.

### Why Pre-populated Tasks Are High-Level
Granular task breakdowns (e.g., "Create header component", "Style navigation links") are too detailed for onboarding and will change as the project evolves. High-level milestones (e.g., "Design homepage mockup", "Client review — round 1") give structure without false precision.

---

## 13. Claude Code Implementation Notes

### What's Fixed
- The four outputs: project tasks, project brief, onboarding checklist, sitemap draft
- Tasks linked to lead via `lead_id`
- Lead status updated to "active"
- `project_path` set in lead row
- Placeholder approach for missing information (same as Proposal Builder)
- Files saved to reports directory, database stores metadata
- Email draft is optional, chat output only
- Activity logging: `project_started`, `task_created` (for each task)

### What Claude Code Has Freedom On
- Exact SKILL.md wording and structure
- How to present the onboarding checklist format
- The specific default tasks to pre-populate in the project database
- How to generate the sitemap from discovery notes (what logic, how much detail)
- The project brief format (follow the structure in §5, but specific wording is flexible)
- How to handle the "no proposal" scenario
- Error handling specifics
