# Skill Polisher V2 — Bundle Support Notes

Notes gathered while polishing the WebClient Studio bundle (2026-04-30). These are observations about what the polisher gets wrong or misses when dealing with bundles vs standalone skills.

## Core Problem

The polisher assumes each skill is independent. Bundles have:
- Shared infrastructure (scripts, config dirs, env vars)
- Cross-skill data contracts (field names, file paths, report formats)
- Entry point skills vs secondary skills
- A parent README/entry SKILL.md that routes to sub-skills

## Specific Gaps Found

### 1. Cross-skill data contracts
The polisher could accidentally rename or move content that defines a data contract. Example: `qualification_report_path` is referenced by proposal-builder and project-onboarder. If the polisher moved the db_helper field documentation to references/, downstream skills would break because the LLM wouldn't know the field names.

**V2 idea:** The polisher should scan other SKILL.md files in the bundle for references to field names, paths, and variable names before moving content.

### 2. Shared infrastructure sections
Every bundle skill has a "Tools" or "Setup" section referencing `$WEBCLIENT_STUDIO_CONFIG_DIR` and shared scripts. These are boilerplate but critical — the LLM needs them to run the skill. The polisher currently treats these as candidates for compression, but for bundles they should probably be standardized.

**V2 idea:** A "bundle manifest" concept — a shared section that gets included in every skill automatically, so the polisher doesn't touch it.

### 3. Entry point vs secondary skill distinction
Lead-qualifier is an entry point — users trigger it directly. Pipeline-tracker, proposal-builder, and project-onboarder are secondary — they're usually reached via the parent SKILL.md router or from another skill's output. The polisher should know this because:
- Entry point skills need trigger phrases in the description
- Secondary skills don't need as much "why" context
- Entry points are the first thing users see on Agensi/ClawHub

**V2 idea:** A `role: entry-point | secondary` field in frontmatter that the polisher reads.

### 4. Internal cross-references
The lead-qualifier SKILL.md contains references to internal architecture docs ("per architecture / lead-qualifier §5.1"). These are stale references to design docs that users don't have access to. The polisher should clean these up but currently doesn't detect them.

**V2 idea:** Detect and remove internal architecture references (§X.Y format, `design-philosophy.md` mentions, architecture doc references).

### 5. Edge cases that are critical paths
In bundles, some "edge cases" are actually critical flows used by other skills. The lead-qualifier's "already exists in pipeline" and "add from existing report" flows are used by proposal-builder when it auto-adds a lead. The polisher moved these to references/ in the standalone version, but for bundles they should stay inline.

**V2 idea:** The polisher should ask: "Is this edge case referenced by another skill in the bundle?" before moving it.

### 6. Report template duplication
The report template appears in both the bundle lead-qualifier and the standalone version. When polishing both, they can drift. For bundles, the report format is a shared contract.

**V2 idea:** A "templates" directory that the polisher can reference, so report formats stay synchronized.

## What Worked Well

- Emoji section anchors work great for both standalone and bundle
- Code blocks for tables are much more readable on Agensi
- Compressing the scoring table from markdown to code block saved space without losing clarity
- The audit checklist caught every important thing

## What Needs Improvement

- The audit guide has no "bundle awareness" section
- No concept of "don't move this — other skills depend on it"
- No detection of stale internal architecture references
- No way to mark content as "bundle boilerplate" vs "skill-specific"
