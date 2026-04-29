# WebClient Studio — Lead to Launch

A skill bundle for freelance web designers. Qualify leads, generate proposals, onboard clients, and track your pipeline — all through your AI agent.

**Minimal setup. No API keys. No external services.** Everything runs locally.

## What's Included

| Skill | What It Does |
|---|---|
| **Lead Qualifier** | Research a company's website, score their fit (1-10), and add them to your pipeline |
| **Proposal Builder** | Turn discovery call notes into a scoped, professional proposal document |
| **Project Onboarder** | Generate a project brief, onboarding checklist, sitemap draft, and task set |
| **Pipeline Tracker** | View, manage, and query your entire pipeline — statuses, follow-ups, tags, tasks, export |

## Install

Clone or download the bundle and place the four skill folders (`lead-qualifier`, `proposal-builder`, `project-onboarder`, `pipeline-tracker`) in your agent's skills directory. On first use, each skill detects the shared scripts and sets up automatically — no manual configuration needed.

Optional: install Playwright + Chromium for better research on JS-rendered websites (`pip install playwright && playwright install chromium`). The Lead Qualifier works without it but produces lower-quality results on modern sites.
### Cross-Agent Compatibility

All paths resolve through the `WEBCLIENT_STUDIO_CONFIG_DIR` environment variable. On first use, the agent asks where to store data, configures the env var automatically, and persists it to your shell config — no manual configuration needed.

```bash
# Set automatically by the agent during setup — you don't need to do this manually
export WEBCLIENT_STUDIO_CONFIG_DIR=/path/to/your/preferred/dir
```

This works across OpenClaw, Claude Code, Codex CLI, Cursor, and any agent with file system access and shell support.

## Quick Start

After install, try these in your agent:

```
"qualify this lead: https://acmeplumbing.ie"
"build a proposal for Acme Plumbing"
"set up project for Acme Plumbing"
"show my pipeline"
```

## How It Works

- **Local SQLite database** at `$WEBCLIENT_STUDIO_CONFIG_DIR/pipeline.db` — auto-created on first use
- **Reports** saved as markdown files in `$WEBCLIENT_STUDIO_CONFIG_DIR/reports/`
- **No cloud services, no API keys, no subscriptions** — your data stays on your machine
- **Export to CSV or JSON** anytime for Notion, Google Sheets, or backup

## Requirements

- Python 3.8+
- An AI agent that supports SKILL.md files (OpenClaw, Claude Code, Codex CLI, etc.)
- `requests` and `beautifulsoup4` for web research (`pip install requests beautifulsoup4`)
- `playwright` (optional, for JS-rendered websites — `pip install playwright && playwright install chromium`)

## Directory Structure

```
$WEBCLIENT_STUDIO_CONFIG_DIR/
├── pipeline.db          # Your pipeline database
├── config.json          # Your preferences
├── shared/              # Python modules (auto-installed)
├── references/          # Templates (auto-installed)
├── reports/
│   ├── qualifications/  # Lead qualification reports
│   ├── proposals/       # Proposal documents
│   ├── projects/        # Project briefs, checklists, sitemaps
│   └── clients/         # Per-client folders (all reports for a client)
└── exports/             # CSV/JSON exports
```

## License

See LICENSE file.
