# Freelance Forge — First Run Setup

This file contains the setup instructions for the agent to execute. A skill should only reach this file if the guard clause fails (see below).

## Guard Clause

Before any skill flow, check if setup has been completed:

```bash
python3 -c "import sys; sys.path.insert(0, '$HOME/.freelance-forge/shared'); import db_helper" 2>/dev/null && echo "OK"
```

If this prints `OK`, skip everything below and proceed with the skill flow.

If this fails, execute the setup steps below.

---

## Setup Steps

### Step 1: Locate the bundle source

The shared scripts and references need to be copied to `~/.freelance-forge/`. Find them by checking these locations in order:

1. `$FREELANCE_FORGE_BUNDLE_DIR/` (if set — Agensi or user may define this)
2. The directory two levels up from this SKILL.md's location (`../../shared/`, `../../references/`)
3. `$HOME/Downloads/freelance-forge/` or `$HOME/Desktop/freelance-forge/` (common download locations)
4. Ask the user: "Where did you download the Freelance Forge bundle?"

Once found, confirm both `shared/` and `references/` exist at that location.

### Step 2: Create the data directory

```bash
mkdir -p ~/.freelance-forge/{reports/{qualifications,proposals,projects},exports}
```

### Step 3: Copy shared scripts

```bash
cp -r <bundle-source>/shared/* ~/.freelance-forge/shared/
```

Verify:
```bash
ls ~/.freelance-forge/shared/db_helper.py
```

### Step 4: Copy references

```bash
cp -r <bundle-source>/references/* ~/.freelance-forge/references/
```

Verify:
```bash
ls ~/.freelance-forge/references/proposal-templates/default.md
```

### Step 5: Install Playwright (strongly recommended)

Tell the user:

> Freelance Forge uses Playwright to research company websites. Most modern websites are JavaScript-rendered (React, Next.js, Vue) and cannot be properly read without it. This is a ~150MB install. You can skip it, but the Lead Qualifier will produce lower-quality results on most websites.

Ask: "Install Playwright now?"

If yes:
```bash
pip3 install playwright && python3 -m playwright install chromium
```

If the user says no or pip isn't available:
- Note that Playwright is not installed
- The Lead Qualifier will use HTTP fallback (works for static sites, reports honestly on JS-only sites)
- The user can install it later by running the same pip command
- Do NOT mention Playwright again in future interactions — it's been communicated

If pip fails:
- Check if `pip3` or `pip` exists
- Suggest installing Python 3 from python.org if neither exists
- Continue without Playwright

### Step 6: Verify

```bash
PYTHONPATH="$HOME/.freelance-forge/shared" python3 -m db_helper paths
```

This should print a JSON object with `config_dir`, `shared_dir`, `db`, and `config` paths. If it fails, something went wrong in Steps 2-4 — troubleshoot.

### Step 7: Tell the user

> Setup complete. Your pipeline database and config are at `~/.freelance-forge/`. You're ready to go.

Then proceed with the original skill flow that triggered setup.

---

## Notes

- This setup only runs **once**. After Step 6 succeeds, the guard clause will pass for all future interactions.
- The database (`pipeline.db`) and config (`config.json`) are created automatically on first use — they do NOT need to be created during setup.
- Re-running setup is safe — it overwrites shared scripts and references but does NOT touch the database, config, reports, or exports.
- On Windows (PowerShell), replace `mkdir -p` with `New-Item -ItemType Directory -Force`, and `cp -r` with `Copy-Item -Recurse -Force`.
- **Windows Python command:** native Windows installs Python as `python` or `py -3`, not `python3`. If a `python3` command fails with "command not found", substitute `python` or `py -3`. The installer detects this and prints a note. This applies to every command in this setup file *and* every command inside the SKILL.md files.
