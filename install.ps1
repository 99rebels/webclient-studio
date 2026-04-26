# Freelance Forge — install script (Windows PowerShell)
# Copies skills to the agent's skills directory and shared scripts/references to ~/.freelance-forge/

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- Detect target skills directory ---
function Get-SkillsDir {
    $candidates = @(
        "$env:USERPROFILE\.openclaw\skills",
        "$env:USERPROFILE\.claude\skills"
    )
    foreach ($dir in $candidates) {
        if (Test-Path $dir) {
            return $dir
        }
    }
    $userDir = Read-Host "Could not auto-detect skills directory. Enter the path"
    return $userDir
}

$SkillsDir = Get-SkillsDir
$DataDir = if ($env:FREELANCE_FORGE_CONFIG_DIR) { $env:FREELANCE_FORGE_CONFIG_DIR } else { "$env:USERPROFILE\.freelance-forge" }

Write-Host "=== Freelance Forge Installer ==="
Write-Host "Skills directory: $SkillsDir"
Write-Host "Data directory:   $DataDir"
Write-Host ""

# --- Create data directory tree ---
@("reports\qualifications", "reports\proposals", "reports\projects", "exports") | ForEach-Object {
    New-Item -ItemType Directory -Path "$DataDir\$_" -Force | Out-Null
}

# --- Copy shared scripts ---
$SharedDest = "$DataDir\shared"
New-Item -ItemType Directory -Path $SharedDest -Force | Out-Null
Copy-Item "$ScriptDir\shared\__init__.py" "$SharedDest\" -Force
Copy-Item "$ScriptDir\shared\db_helper.py" "$SharedDest\" -Force
Copy-Item "$ScriptDir\shared\web_research.py" "$SharedDest\" -Force
Copy-Item "$ScriptDir\shared\templates.py" "$SharedDest\" -Force
Write-Host "✓ Shared scripts installed to $SharedDest"

# --- Copy references ---
$RefsDest = "$DataDir\references"
New-Item -ItemType Directory -Path $RefsDest -Force | Out-Null
Copy-Item "$ScriptDir\references\*" "$RefsDest\" -Recurse -Force
Write-Host "✓ Reference templates installed to $RefsDest"

# --- Copy skills ---
$skillNames = @("lead-qualifier", "proposal-builder", "project-onboarder", "pipeline-tracker")
foreach ($skill in $skillNames) {
    $src = "$ScriptDir\skills\$skill"
    if (Test-Path $src) {
        $dest = "$SkillsDir\$skill"
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        Copy-Item "$src\SKILL.md" "$dest\" -Force
        Write-Host "✓ $skill installed to $dest\"
    } else {
        Write-Host "⚠ $skill not found in source — skipping"
    }
}

# --- Detect Python launcher (Windows-friendly) ---
# Native Windows usually has 'python' or 'py -3'; 'python3' rarely exists.
function Find-PythonCmd {
    foreach ($cand in @(@("py","-3"), @("python"), @("python3"))) {
        try {
            & $cand[0] $cand[1..($cand.Length-1)] --version 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $cand }
        } catch {}
    }
    return $null
}
$PythonCmd = Find-PythonCmd

# --- Verify ---
Write-Host ""
Write-Host "=== Verifying installation ==="
$env:PYTHONPATH = $SharedDest
if ($null -eq $PythonCmd) {
    Write-Host "  ⚠ Python 3 not found on PATH — install from python.org and re-run."
    Write-Host "    Note: SKILL.md files invoke 'python3' which may need to be 'python' or 'py -3' on Windows."
} else {
    & $PythonCmd[0] $PythonCmd[1..($PythonCmd.Length-1)] -c "import db_helper" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Python modules import successfully (using: $($PythonCmd -join ' '))"
    } else {
        Write-Host "  ⚠ Could not import db_helper — check the install copied to $SharedDest"
    }

    & $PythonCmd[0] $PythonCmd[1..($PythonCmd.Length-1)] -c "import requests" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ⚠ 'requests' not installed — run: $($PythonCmd -join ' ') -m pip install requests beautifulsoup4"
    }

    # Heads-up: SKILL.md files use 'python3'. On Windows that may not resolve.
    if ($PythonCmd[0] -ne "python3") {
        Write-Host ""
        Write-Host "  ℹ NOTE: This system uses '$($PythonCmd -join ' ')' but the SKILL.md files reference 'python3'."
        Write-Host "    If commands fail when the agent runs them, ask the agent to substitute '$($PythonCmd -join ' ')' for 'python3'."
    }
}

Write-Host ""
Write-Host "=== Installation complete ==="
Write-Host ""
Write-Host '  "qualify this lead: https://example.com"'
Write-Host '  "build a proposal for Acme"'
Write-Host '  "set up project for Acme"'
Write-Host '  "show my pipeline"'
Write-Host ""
Write-Host "All data lives in: $DataDir"
Write-Host "Re-run this script anytime to upgrade in place (your data is never touched)."
