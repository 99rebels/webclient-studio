# WebClient Studio — First Run Setup

This file contains the setup instructions for the agent to execute. A skill should only reach this file if the guard clause fails (see below).

## Guard Clause

Before any skill flow, run:

```bash
python3 -c "import sys,os; os.environ.get('WEBCLIENT_STUDIO_CONFIG_DIR') or exit(1); sys.path.insert(0, os.environ['WEBCLIENT_STUDIO_CONFIG_DIR']+'/shared'); import db_helper" 2>/dev/null && echo OK
```

If this prints `OK`, skip everything below and proceed with the skill flow.

If it fails, execute the setup steps below **in order**.

---

## Setup Steps

### Step 1: Locate the bundle source

The shared scripts, references, and skill files need to be installed. Find the bundle source by checking these locations in order:

1. `$WEBCLIENT_STUDIO_BUNDLE_DIR/` (if set — Agensi or user may define this)
2. The directory two levels up from this SKILL.md's location (`../../shared/`, `../../references/`, `../../skills/`)
3. `$HOME/Downloads/webclient-studio/` or `$HOME/Desktop/webclient-studio/` (common download locations)
4. Ask the user: "Where did you download the WebClient Studio bundle?"

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

Also note which agent platform was detected (used in Step 3 for the default suggestion):
- If `$HOME/.openclaw/skills/` → platform is **OpenClaw**
- If `$HOME/.claude/skills/` → platform is **Claude Code**
- Otherwise → platform is **unknown**

### Step 3: Choose the data directory

The agent **MUST ask the user** where to store pipeline data, reports, and exports. Present a default suggestion based on the agent platform detected in Step 2:

| Platform detected | Suggested default |
|---|---|
| OpenClaw | `$HOME/.openclaw/workspace/webclient-studio/` |
| Claude Code | `$HOME/.claude/webclient-studio/` |
| Other / unknown | `$HOME/.webclient-studio/` |

Example prompt to the user:

> "Where should I store your pipeline data, reports, and exports? I'd suggest `[default-for-detected-agent]` but you can pick any directory."

The user can choose ANY path — they are not limited to the suggestion.

Once the user confirms (or provides a custom path), set a variable and create the directory structure:

```bash
DATA_DIR="<user-chosen-or-default-path>"
mkdir -p "$DATA_DIR"/{shared,references,exports}
mkdir -p "$DATA_DIR"/reports/{qualifications,proposals,projects,clients}
```

### Step 4: Configure the env var automatically

The agent writes the `WEBCLIENT_STUDIO_CONFIG_DIR` env var to the user's shell config so it persists across sessions:

```bash
# Detect shell config file
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.bash_profile" ]; then SHELL_RC="$HOME/.bash_profile"
else SHELL_RC="$HOME/.bashrc"  # create if none exists
fi

# Add env var if not already present
grep -q "WEBCLIENT_STUDIO_CONFIG_DIR" "$SHELL_RC" 2>/dev/null || echo "export WEBCLIENT_STUDIO_CONFIG_DIR=\"$DATA_DIR\"" >> "$SHELL_RC"
```

Tell the user: "Added `WEBCLIENT_STUDIO_CONFIG_DIR` to your `$SHELL_RC`. This will take effect in new terminal sessions. For this session, I'll use it directly."

Then export it for the current session:
```bash
export WEBCLIENT_STUDIO_CONFIG_DIR="$DATA_DIR"
```

### Step 5: Copy shared scripts

```bash
cp -r "$BUNDLE_SOURCE/shared/"* "$DATA_DIR/shared/"
```

Verify:
```bash
ls "$DATA_DIR/shared/db_helper.py" "$DATA_DIR/shared/web_research.py" "$DATA_DIR/shared/templates.py"
```

All three files must exist. If any are missing, the copy failed — troubleshoot before continuing.

### Step 6: Copy references

```bash
cp -r "$BUNDLE_SOURCE/references/"* "$DATA_DIR/references/"
```

Verify:
```bash
ls "$DATA_DIR/references/proposal-templates/default.md"
```

### Step 7: Copy skill files to the agent's skills directory

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

### Step 8: Install Python dependencies

Check if the required Python packages are installed:

```bash
python3 -c "import requests; from bs4 import BeautifulSoup; print('OK')" 2>/dev/null && echo "DEPS_OK" || echo "DEPS_MISSING"
```

If `DEPS_MISSING`, install them:
```bash
pip3 install requests beautifulsoup4
```

If `pip3` isn't available, try `pip`. If neither exists, tell the user Python 3 is required and they can install it from python.org.

### Step 9: Install Playwright

**You MUST always ask the user about Playwright. Do not skip this step. Do not silently decide to skip it.**

Tell the user:

> WebClient Studio uses Playwright to research company websites. Most modern websites are JavaScript-rendered (React, Next.js, Vue) and cannot be properly read without it. This is a ~150MB install. **You can skip it, but the Lead Qualifier will produce lower-quality results on most websites.** It is highly recommended to install it now.

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

### Step 10: Verify everything

Run all checks. All must pass:

```bash
# 1. Env var is set
source "$SHELL_RC" 2>/dev/null
echo "$WEBCLIENT_STUDIO_CONFIG_DIR"

# 2. Python module imports
python3 -c "import sys; sys.path.insert(0, '$WEBCLIENT_STUDIO_CONFIG_DIR/shared'); import db_helper; print('db_helper: OK')"

# 3. Config and DB paths resolve
python3 -c "
import sys; sys.path.insert(0, '$WEBCLIENT_STUDIO_CONFIG_DIR/shared')
import db_helper
print('Config dir:', db_helper.get_config_dir())
print('DB path:', db_helper.db_path())
print('Shared dir:', db_helper.get_shared_dir())
"

# 4. Python deps available
python3 -c "import requests; from bs4 import BeautifulSoup; print('deps: OK')"
```

If any check fails, troubleshoot before continuing. Common issues:
- Env var not set — re-run Step 4
- Wrong `PYTHONPATH` — confirm `$WEBCLIENT_STUDIO_CONFIG_DIR/shared/` contains `db_helper.py`
- Missing pip packages — re-run Step 8
- Python 3 not found — install from python.org

### Step 11: Tell the user

> Setup complete. Your pipeline data is stored at `$DATA_DIR`. The `WEBCLIENT_STUDIO_CONFIG_DIR` env var has been added to your `$SHELL_RC`.

Then proceed with the original skill flow that triggered setup.

---

## Notes

- This setup only runs **once**. After Step 10 succeeds, the guard clause will pass for all future interactions.
- The database (`pipeline.db`) and config (`config.json`) are created automatically on first use — they do NOT need to be created during setup.
- Re-running setup is safe — it overwrites shared scripts, references, and skill files but does NOT touch the database, config, reports, or exports.
- On Windows (PowerShell), replace `mkdir -p` with `New-Item -ItemType Directory -Force`, and `cp -r` with `Copy-Item -Recurse -Force`.

### About the env var approach

All four SKILL.md files and the Python modules use `$WEBCLIENT_STUDIO_CONFIG_DIR` everywhere. There is no hardcoded default path — the env var is always set after setup. The agent should always source the shell config or use the env var. If the env var is not set, the guard clause will fail and the agent will be directed to run setup.
