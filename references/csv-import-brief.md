# CSV Import Feature — Implementation Brief

**Status:** Not yet implemented
**Created:** 2026-04-28
**Author:** Cambrian (from conversation with Rian)

---

## Context

Freelance Forge can export the pipeline as CSV (`db_helper export --format csv`). Rian wants the reverse: import a CSV of leads into the pipeline. Use case is a freelancer switching from a spreadsheet, Trello, or another CRM who already has a list of companies/contacts.

## Decision: Agent-driven import, no new Python code

The import flow should live in the **Pipeline Tracker** SKILL.md as a new section (§K). The agent reads the CSV, proposes a column mapping, previews the results, and calls the existing `add-lead` command for each row. No changes to `db_helper.py` needed.

## Design

### Flow

1. **User provides CSV** — file path or drops the file
2. **Agent reads headers + sample rows** (first 3-5 rows)
3. **Agent proposes column mapping** — shows a table mapping their columns to our DB fields. Columns that don't match our schema are marked "skip". User confirms or adjusts.
4. **Preview** — agent shows how a few rows will import (company, website, score, status — whatever was mapped). Flags any issues (missing required field "company", invalid score values, etc.)
5. **User says go** — agent calls `add-lead` for each row
6. **Summary** — "Imported 23 leads. 2 skipped (duplicates). 1 had invalid score (set to NULL)."

### Rules

- **Only import columns that map to existing DB fields.** No new columns created. If their CSV has a "Revenue" column and we don't have one, it gets skipped (or optionally mapped to `research_notes` as context if the user wants).
- **Existing DB fields** (the only valid targets): `company`, `website`, `contact_name`, `contact_email`, `status`, `lead_score`, `data_confidence`, `research_notes`, `pitch_notes`, `tags`
- **Required field:** `company` — if a row has no company name, skip it and flag
- **Defaults for unmapped fields:**
  - `status` → `"lead"`
  - `lead_score` → `NULL` (don't import arbitrary scores without validation)
  - `data_confidence` → `"LOW"` (imported data hasn't been verified by us)
  - `tags` → `"imported"` (so imported leads are always identifiable)
- **Duplicate check:** Before each `add-lead`, run `get-lead --company` — if it exists, skip and flag
- **Validation:** Scores must be 1-10 integers or NULL. URLs should look like URLs. Statuses must match our valid status list.
- **Cap:** Suggest importing max 50 rows per batch to avoid token burn. If more, offer to process in batches.
- **Activity log:** Each imported lead gets `lead_imported` in the activity log with the source file name

### What NOT to do

- No auto-import without user confirming the mapping
- No guessing values for unmapped columns
- No importing score values without validating they're 1-10
- No overwriting existing leads silently
- No creating new database columns to match their CSV

### Storage

Save imported CSVs to `~/.freelance-forge/imports/` so they can be referenced later (which rows came from which file, when).

## Implementation steps

1. Add §K Import section to `skills/pipeline-tracker/SKILL.md`
2. Add trigger phrases to the routing table in Pipeline Tracker ("import CSV", "import leads", "upload spreadsheet")
3. Pull request and push to GitHub

## No Python changes needed

This entire feature is a SKILL.md update. The agent does the CSV parsing, column matching, and row-by-row insertion using existing `db_helper` commands. The agent's natural language understanding is better at fuzzy column matching than a rigid Python import script anyway.
