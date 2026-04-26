#!/usr/bin/env bash
set -euo pipefail

# Freelance Forge — install script (macOS / Linux / WSL)
# Copies skills to the agent's skills directory and shared scripts/references to ~/.freelance-forge/

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Detect target skills directory ---
detect_skills_dir() {
    for dir in "$HOME/.openclaw/skills" "$HOME/.claude/skills"; do
        if [ -d "$dir" ]; then
            echo "$dir"
            return 0
        fi
    done
    echo ""
    echo "Could not auto-detect your agent's skills directory."
    echo "Common locations:"
    echo "  ~/.openclaw/skills/    (OpenClaw)"
    echo "  ~/.claude/skills/      (Claude Code)"
    echo ""
    printf "Enter the path to your skills directory: "
    read -r user_dir
    echo "$user_dir"
}

SKILLS_DIR="$(detect_skills_dir)"
DATA_DIR="${FREELANCE_FORGE_CONFIG_DIR:-$HOME/.freelance-forge}"

echo "=== Freelance Forge Installer ==="
echo "Skills directory: $SKILLS_DIR"
echo "Data directory:   $DATA_DIR"
echo ""

# --- Create data directory tree ---
mkdir -p "$DATA_DIR/reports/qualifications"
mkdir -p "$DATA_DIR/reports/proposals"
mkdir -p "$DATA_DIR/reports/projects"
mkdir -p "$DATA_DIR/exports"

# --- Copy shared scripts ---
SHARED_DEST="$DATA_DIR/shared"
mkdir -p "$SHARED_DEST"
cp "$SCRIPT_DIR/shared/__init__.py" "$SHARED_DEST/"
cp "$SCRIPT_DIR/shared/db_helper.py" "$SHARED_DEST/"
cp "$SCRIPT_DIR/shared/web_research.py" "$SHARED_DEST/"
cp "$SCRIPT_DIR/shared/templates.py" "$SHARED_DEST/"
echo "✓ Shared scripts installed to $SHARED_DEST"

# --- Copy references ---
REFS_DEST="$DATA_DIR/references"
mkdir -p "$REFS_DEST"
cp -r "$SCRIPT_DIR/references/"* "$REFS_DEST/"
echo "✓ Reference templates installed to $REFS_DEST"

# --- Copy skills ---
SKILL_NAMES=("lead-qualifier" "proposal-builder" "project-onboarder" "pipeline-tracker")
for skill in "${SKILL_NAMES[@]}"; do
    if [ -d "$SCRIPT_DIR/skills/$skill" ]; then
        mkdir -p "$SKILLS_DIR/$skill"
        cp "$SCRIPT_DIR/skills/$skill/SKILL.md" "$SKILLS_DIR/$skill/"
        echo "✓ $skill installed to $SKILLS_DIR/$skill/"
    else
        echo "⚠ $skill not found in source — skipping"
    fi
done

# --- Verify ---
echo ""
echo "=== Verifying installation ==="
if PYTHONPATH="$SHARED_DEST" python3 -c "import db_helper; print('  db_helper: OK')" 2>/dev/null; then
    echo "  ✓ Python modules import successfully"
else
    echo "  ⚠ Could not import db_helper — check Python 3 is installed"
fi

if ! python3 -c "import requests" 2>/dev/null; then
    echo "  ⚠ 'requests' not installed — run: pip3 install requests beautifulsoup4"
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Quick start:"
echo '  "qualify this lead: https://example.com"'
echo '  "build a proposal for Acme"'
echo '  "set up project for Acme"'
echo '  "show my pipeline"'
echo ""
echo "All data lives in: $DATA_DIR"
echo "Re-run this script anytime to upgrade in place (your data is never touched)."
