# Claude's Bundle — Cambrian's Review

## Overall Assessment: Strong work. A few structural problems to fix.

Claude built real, functional code. The SKILL.md files are detailed and well-written. The db_helper.py is solid. The web_research.py is genuinely well-designed (Playwright-first with HTTP fallback, source-annotated extraction, honest failure handling). The CLI shim approach is smart — it keeps SKILL.md files free of inline Python.

But there are real problems with the distribution model that need solving before this can ship.

---

## Problem 1: The installer assumes repo-based install, not Agensi/ClawHub

Both `install.sh` and `install.ps1` are designed for someone who cloned the repo and runs `./install.sh`. They:
- Copy from a `skills/` source directory to the agent's skills directory
- Copy `shared/` to `freelance_forge_shared/` next to the skills
- Copy `references/` to `freelance_forge_references/`
- Offer to install Playwright via pip

This is NOT how Agensi or ClawHub works. On Agensi:
- The user buys the bundle
- They get the files (via download or the platform's install mechanism)
- The platform puts each SKILL.md in the right place
- Shared scripts and references need to be accessible to the skills

The install scripts are still useful (someone might clone the GitHub repo), but they can't be the primary install path. The SKILL.md files need to work WITHOUT the installer having run first.

### How the SKILL.md files reference shared scripts currently:

```bash
SHARED="${FREELANCE_FORGE_SHARED_DIR:-$(dirname "$0")/../../freelance_forge_shared}"
PYTHONPATH="$(dirname "$SHARED")" python3 -m freelance_forge_shared.db_helper <command>
```

This has a problem: `$(dirname "$0")` doesn't work reliably when the agent invokes the skill. The agent doesn't run `SKILL.md` as a script — it reads it as instructions and follows them. `$0` is meaningless in that context.

### What needs to happen:

The SKILL.md files should reference the shared scripts via `$FREELANCE_FORGE_SHARED_DIR` with a clear default path. Something like:

```bash
SHARED="${FREELANCE_FORGE_SHARED_DIR:-~/.freelance-forge/shared}"
python3 -m freelance_forge_shared.db_helper <command>
```

The install script (or Agensi's install process) places the shared folder at `~/.freelance-forge/shared/`. The `PYTHONPATH` resolution happens inside the shared modules themselves, not in the SKILL.md instructions.

Actually, looking at the code again — the `get_shared_dir()` function in `db_helper.py` already resolves via `__file__`, which means the shared directory just needs to be on the Python path. The SKILL.md instructions should be simpler.

---

## Problem 2: Shared scripts + references need to live somewhere specific

When ClawHub or Agensi installs four individual SKILL.md files, they end up in the agent's skills directory — each in their own folder. But `shared/` and `references/` need to live somewhere all four skills can find them.

### Options:

**A) Put everything in `~/.freelance-forge/`** (my preferred approach)
```
~/.freelance-forge/
├── pipeline.db
├── config.json
├── shared/              # db_helper.py, web_research.py, templates.py
├── references/          # templates, email drafts, checklists
├── reports/
└── exports/
```

The install script creates `~/.freelance-forge/shared/` and `~/.freelance-forge/references/`. Each SKILL.md references them via `$FREELANCE_FORGE_CONFIG_DIR` (which already defaults to `~/.freelance-forge/`).

**B) Put shared in the skills directory**
```
~/.openclaw/skills/
├── lead-qualifier/SKILL.md
├── pipeline-tracker/SKILL.md
├── freelance_forge_shared/
└── freelance_forge_references/
```

This works but is messy — pollutes the skills directory with non-skill folders.

**C) pip install as a package**
```
pip install freelance-forge-shared
```

Then SKILL.md just does `python3 -m freelance_forge_shared.db_helper`. Clean but adds a pip install step.

### My recommendation: Option A

It's the simplest. The install script creates the directories. The SKILL.md files reference `$FREELANCE_FORGE_CONFIG_DIR/shared/`. Everything lives in one place. No Python path tricks needed — just `PYTHONPATH="$FREELANCE_FORGE_CONFIG_DIR/shared" python3 -m db_helper`.

---

## Problem 3: Claude applied corrections to architecture docs but the sub-skill docs weren't updated

Claude built the SKILL.md files from scratch (good), but the architecture docs it updated still have some stale content. Specifically:

- `architecture.md` line 42: "Whether data lives in Notion or locally" — should just say "the local approach has zero friction"
- `architecture.md` line 56: "Tags give users the categorisation flexibility that Notion's select properties provided" — fine for historical context, no change needed
- `architecture.md` lines 555+: The "Why Each Sub-Skill Standalone" etc. blocks — need to verify the duplicate was removed (the grep shows they appear once, so correction #1 was applied ✅)
- `architecture.md`: No "irreversible" found ✅ (correction #2 applied)

But the sub-skill deep dives (lead-qualifier.md, proposal-builder.md, etc.) in the repo — were corrections 3-9 applied? Need to check. The SKILL.md files are new builds from scratch, so they're clean. The deep-dive .md files in the project docs are separate.

---

## Problem 4: The CLI shim approach has a path problem

The SKILL.md files say:
```bash
PYTHONPATH="$(dirname "$SHARED")" python3 -m freelance_forge_shared.db_helper <command>
```

But `freelance_forge_shared` needs to be a valid Python package (has `__init__.py`) AND be importable. The `PYTHONPATH` needs to point to the *parent* of `freelance_forge_shared/`, not the directory itself.

If the shared folder is at `~/.freelance-forge/shared/freelance_forge_shared/`:
- `PYTHONPATH=~/.freelance-forge/shared` works
- `PYTHONPATH=~/.freelance-forge/shared/freelance_forge_shared` does NOT work

The SKILL.md instructions need to be precise about this. Or better yet, make the shared modules work without `PYTHONPATH` by resolving the path internally.

---

## Problem 5: The corrections doc was included in the repo

Claude committed `corrections.md` to the repo. That's a working doc, not something that should ship. Remove it before publishing.

---

## What's Good (genuinely)

### db_helper.py
- Clean, well-structured, follows the architecture spec
- Transaction handling is correct (BEGIN/COMMIT/ROLLBACK in context manager)
- Activity logging is enforced at the wrapper level, not left to callers
- `update_lead_status` correctly updates `status_since` and `date_updated`
- `record_follow_up` correctly does NOT touch `status_since` (correction #13 applied)
- `get_stale_leads` uses `MAX(status_since, last_follow_up)` (correction #13 applied)
- Dry-run support on all write functions
- Fuzzy match is correctly implemented as case-insensitive LIKE
- Export functions produce clean CSV and JSON
- Config management is simple and correct
- CLI shim covers all functions — comprehensive
- UUID primary keys, ISO 8601 timestamps, proper foreign keys with CASCADE

### web_research.py
- The Playwright-first / HTTP-fallback pattern is exactly right
- Source-annotated extraction (`Fact` dataclass with claim, source_section, source_url, confidence) is excellent
- Tech stack detection covers the major platforms
- Social link extraction is thorough
- Contact extraction (emails, phones) with reasonable filtering
- Honest failure handling — `accessible=False` with human-readable notes
- The `missing` list tells the agent what it should flag as Unverified
- Suggested tags generated from tech stack detection

### templates.py
- Minimal, correct, no over-engineering
- Section blocks ({{#section}}...{{/section}}) handle lists and dicts
- Dotted lookup for nested context (client.name)
- Reference search paths are comprehensive (env var, installed layout, source layout, symlink)
- CLI render with --out flag writes to disk and prints path — clean

### SKILL.md files
- Lead Qualifier: comprehensive, honest scoring rules, mandatory Unverified section, clear anti-hallucination rules
- Proposal Builder: good pricing guidance, placeholder approach for gaps, first-run pricing strategy
- Project Onboarder: proper brief/checklist/sitemap structure, task pre-population, edge cases covered
- Pipeline Tracker: complete query interface, stale lead detection, task management, export

### Reference templates
- Proposal template covers all six sections from the architecture
- Email drafts are short and contextual (not generic)
- Onboarding checklist has the four sections (Assets, Access, Information, Approvals)

---

## Summary of what needs fixing

| Priority | Issue | Fix |
|---|---|---|
| **Critical** | Install model doesn't match Agensi/ClawHub distribution | Decide on shared script location (recommend `~/.freelance-forge/shared/`), update SKILL.md path references, update install script |
| **Critical** | SKILL.md `$0` path resolution doesn't work when agent reads instructions | Replace `$(dirname "$0")` with explicit env var or known path |
| **Medium** | PYTHONPATH resolution in SKILL.md needs precision | Document exact path or make modules self-resolving |
| **Low** | corrections.md in repo | Remove before publish |
| **Low** | Minor Notion references in architecture.md | Clean up (2 remaining, both are historical context) |

---

## On the "free Pipeline Tracker on ClawHub" strategy

The current SKILL.md for Pipeline Tracker references `freelance_forge_shared.db_helper`. If someone installs JUST the Pipeline Tracker from ClawHub (free tier), they won't have the shared scripts. Two options:

**A) Bundle the shared scripts with the free skill**
- Pipeline Tracker's ClawHub package includes `db_helper.py` (just that module, not web_research or templates)
- Other sub-skills include all shared scripts
- Some code duplication but each skill works standalone

**B) Shared scripts as a separate ClawHub package**
- `freelance-forge-shared` is its own ClawHub listing
- Pipeline Tracker depends on it
- ClawHub's bundle manifest handles the dependency

I'd go with A for v1. It's simpler and the db_helper.py is only ~500 lines. The full paid bundle includes all four skills plus all shared scripts plus references.

---

## Next steps

1. Decide on shared script location (recommend `~/.freelance-forge/shared/`)
2. Update SKILL.md path references to use the decided location
3. Fix the install script to work for both repo-based and Agensi/ClawHub installs
4. Decide on free-tier distribution model for Pipeline Tracker
5. Remove corrections.md from repo
6. Test the install flow end-to-end
