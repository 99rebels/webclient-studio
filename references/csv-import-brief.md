# CSV Import Feature — Implementation Brief

**Status:** Implemented (SKILL.md updates only — no Python changes)
**Created:** 2026-04-28
**Updated:** 2026-04-29
**Author:** Cambrian (from conversation with Rian)

---

## Context

Freelance Forge can export the pipeline as CSV (`db_helper export --format csv`). Rian wanted the reverse: import a CSV of leads into the pipeline. Use case is a freelancer switching from a spreadsheet, Trello, or another CRM who already has a list of companies/contacts.

## Decision: Agent-driven import, no new Python code

The import flow lives in the **Pipeline Tracker** SKILL.md as §K. The agent reads the CSV, proposes a column mapping, previews the results, and calls the existing `add-lead` command for each row. No changes to `db_helper.py` needed.

## Two-Phase Flow

### Phase 1: Import (Pipeline Tracker §K)
Bulk, fast data ingestion. Leads enter the pipeline with `imported` tag, `LOW` confidence, `lead` status. No research, no reports, no qualification — just data.

### Phase 2: Enrich (Lead Qualifier — Enrichment Mode)
On-demand, per-lead. When the user says "qualify [imported company]", the Lead Qualifier detects it already exists (via `imported` tag), runs full research, and **updates** the existing row instead of creating a new one. Creates client folder at this point, removes `imported` tag, bumps confidence/score based on actual research.

The assumption: if someone manually imported a company, they already want to work with them. Qualification verifies that decision.

## What was implemented

### Pipeline Tracker (`skills/pipeline-tracker/SKILL.md`)
- Added §K Import section
- Added trigger phrases to routing table ("import CSV", "import leads", "upload spreadsheet")
- Full flow: read CSV → show headers + sample → propose mapping → preview 3-5 rows → user confirms → import row-by-row → summary

### Lead Qualifier (`skills/lead-qualifier/SKILL.md`)
- Modified Step 2 (duplicate check) to detect `imported` tag
- Added Enrichment Mode: when an imported lead is qualified, update existing row instead of creating new
- Client folder created during enrichment, not during import
- Removes `imported` tag after successful qualification

### Cleanup
- Deleted `subskills/` directory (stale v0.3 design docs, pre-bundle format)

## Design decisions

| Decision | Rationale |
|---|---|
| Agent-driven, no Python | Agent's fuzzy matching better than rigid import script |
| Human-in-the-loop at mapping step | Prevents garbage data from wrong column mappings |
| Preview 3-5 rows, not all | Avoids token burn on large imports |
| Encoding fallback (latin-1/cp1252) | Excel on Windows often exports non-UTF-8 CSVs |
| `data_confidence → LOW` for imports | Marks data as unverified without creating second-class status |
| `tags → imported` | Filterable, removable after qualification |
| Don't dump skip columns into notes | Prevents noise; only on explicit user request |
| Batch cap of 50 rows | Token management |
| No "add to pipeline?" for enrichment | Import implies intent; qualification verifies it |
| CSV-only (no .xlsx yet) | Right scope for v1; Excel support noted as future |
| Imported CSVs saved to `imports/` | Audit trail for source files |

## No Python changes needed

This entire feature is SKILL.md updates. The agent does CSV parsing, column matching, and row-by-row insertion using existing `db_helper` commands.
