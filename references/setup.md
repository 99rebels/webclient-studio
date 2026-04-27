# Freelance Forge — First Run Setup

This file contains the setup instructions for the agent to execute. A skill should only reach this file if the guard clause fails (see below).

## Guard Clause

Before any skill flow, run:

```bash
python3 -c "import sys; sys.path.insert(0, '$HOME/.freelance-forge/shared'); import db_helper" 2>/dev/null && echo OK
```

If this prints `OK`, skip everything below and proceed with the skill flow.

If it fails, execute the setup steps below **in order**.

---

## Setup Steps

### Step 1: Locate the bundle source

The shared scripts, references, and skill files need to be installed. Find the bundle source by checking these locations in order:

1. `$FREELANCE_FORGE_BUNDLE_DIR/` (if set — Agensi or user may define this)
2. The directory two levels up from this SKILL.md's location (`../../shared/`, `../../references/`, `../../skills/`)
3. `$HOME/Downloads/freelance-forge/` or `$HOME/Desktop/freelance-forge/` (common download locations)
4. Ask the user: "Where did you download the Freelance Forge bundle?"

Once found, confirm all three directories exist at that location:
- `shared/` (Python modules)
- `references/` (templates, email drafts, checklists)
- `skills/` (four SKILL.md folders: `lead-qualifier`, `proposal-builder`, `project-onboarder`, `pipeline-tracker`)

Set a variable for the remaining steps:
```bash
BUNDLE_SOURCE="<path-found-above>"
```

### Step 2: Detect the agent's skills directory

Find where the agent loads skills from:

1. Check if `$HOME/.openclaw/skills/` exists → use it
2. Check if `$HOME/.claude/skills/` exists → use it
3. Ask the user: "What is your agent's skills directory?"

Set a variable:
```bash
SKILLS_DIR="<skills-directory-found-above>"
```

### Step 3: Create all directories

```bash
mkdir -p ~/.freelance-forge/shared
mkdir -p ~/.freelance-forge/references
mkdir -p ~/.freelance-forge/reports/{qualifications,proposals,projects}
mkdir -p ~/.freelance-forge/exports
```

### Step 4: Copy shared scripts

```bash
cp -r "$BUNDLE_SOURCE/shared/"* ~/.freelance-forge/shared/
```

Verify:
```bash
ls ~/.freelance-forge/shared/db_helper.py ~/.freelance-forge/shared/web_research.py ~/.freelance-forge/shared/templates.py
```

All three files must exist. If any are missing, the copy failed — troubleshoot before continuing.

### Step 5: Copy references

```bash
cp -r "$BUNDLE_SOURCE/references/"* ~/.freelance-forge/references/
```

Verify:
```bash
ls ~/.freelance-forge/references/proposal-templates/default.md
```

### Step 6: Copy skill files to the agent's skills directory

Copy each SKILL.md so the agent can load them:

```bash
for skill in lead-qualifier proposal-builder project-onboarder pipeline-tracker; do
    mkdir -p "$SKILLS_DIR/$skill"
    cp "$BUNDLE_SOURCE/skills/$skill/SKILL.md" "$SKILLS_DIR/$skill/"
done
```

Verify:
```bash
ls "$SKILLS_DIR"/lead-qualifier/SKILL.md "$SKILLS_DIR"/proposal-builder/SKILL.md "$SKILLS_DIR"/project-onboarder/SKILL.md "$SKILLS_DIR"/pipeline-tracker/SKILL.md
```

All four files must exist.

### Step 7: Install Python dependencies

Check if the required Python packages are installed:

```bash
python3 -c "import requests; from bs4 import BeautifulSoup; print('OK')" 2>/dev/null && echo "DEPS_OK" || echo "DEPS_MISSING"
```

If `DEPS_MISSING`, install them:
```bash
pip3 install requests beautifulsoup4
```

If `pip3` isn't available, try `pip`. If neither exists, tell the user Python 3 is required and they can install it from python.org.

### Step 8: Install Playwright

**You MUST always ask the user about Playwright. Do not skip this step. Do not silently decide to skip it.**

Tell the user:

> Freelance Forge uses Playwright to research company websites. Most modern websites are JavaScript-rendered (React, Next.js, Vue) and cannot be properly read without it. This is a ~150MB install. **You can skip it, but the Lead Qualifier will produce lower-quality results on most websites.** It is highly recommended to install it now.

Ask: "Install Playwright now?"

**If yes:**
```bash
pip3 install playwright && python3 -m playwright install chromium
```

If the install succeeds, tell the user Playwright is ready.

**If the user says no:**
- Tell them: "OK. The Lead Qualifier will use a fallback method that works on simple/static websites but will produce lower-quality results on JavaScript-heavy sites. You can install it anytime by running: `pip3 install playwright && python3 -m playwright install chromium`"
- **Do NOT mention Playwright again in future interactions** — it has been communicated and declined.

**If pip fails:**
- Check if `pip3` or `pip` exists
- Suggest installing Python 3 from python.org if neither exists
- Continue without Playwright

### Step 9: Verify everything

Run all three checks. All must pass:

```bash
# 1. Python module imports
python3 -c "import sys; sys.path.insert(0, '$HOME/.freelance-forge/shared'); import db_helper; print('db_helper: OK')"

# 2. Config and DB paths resolve
python3 -c "
import sys; sys.path.insert(0, '$HOME/.freelance-forge/shared')
import db_helper
print('Config dir:', db_helper.get_config_dir())
print('DB path:', db_helper.db_path())
print('Shared dir:', db_helper.get_shared_dir())
"

# 3. Python deps available
python3 -c "import requests; from bs4 import BeautifulSoup; print('deps: OK')"
```

If any check fails, troubleshoot before continuing. Common issues:
- Wrong `PYTHONPATH` — confirm `~/.freelance-forge/shared/` contains `db_helper.py`
- Missing pip packages — re-run Step 7
- Python 3 not found — install from python.org

### Step 10: Tell the user

> Setup complete. Your pipeline database and config are at `~/.freelance-forge/`. You're ready to go.

Then proceed with the original skill flow that triggered setup.

---

## Notes

- This setup only runs **once**. After Step 9 succeeds, the guard clause will pass for all future interactions.
- The database (`pipeline.db`) and config (`config.json`) are created automatically on first use — they do NOT need to be created during setup.
- Re-running setup is safe — it overwrites shared scripts, references, and skill files but does NOT touch the database, config, reports, or exports.
- On Windows (PowerShell), replace `mkdir -p` with `New-Item -ItemType Directory -Force`, and `cp -r` with `Copy-Item -Recurse -Force`.
