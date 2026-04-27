# Freelance Forge — Lead to Launch

A skill bundle for freelance web designers. Qualify leads, generate proposals, onboard clients, and track your pipeline — all through your AI agent.

**Zero setup. No API keys. No external services.** Everything runs locally.

## What's Included

| Skill | What It Does |
|---|---|
| **Lead Qualifier** | Research a company's website, score their fit (1-10), and add them to your pipeline |
| **Proposal Builder** | Turn discovery call notes into a scoped, professional proposal document |
| **Project Onboarder** | Generate a project brief, onboarding checklist, sitemap draft, and task set |
| **Pipeline Tracker** | View, manage, and query your entire pipeline — statuses, follow-ups, tags, tasks, export |

## Install

```bash
# Clone or download the bundle, then:
./install.sh
```

The installer will:
1. Detect your agent's skills directory (OpenClaw, Claude Code, or custom)
2. Copy all four skills to the right place
3. Install shared scripts and templates to `~/.freelance-forge/`
4. Optionally install Playwright + Chromium for JS-rendered site research

Re-run anytime to upgrade — your data is never touched.

## Quick Start

After install, try these in your agent:

```
"qualify this lead: https://acmeplumbing.ie"
"build a proposal for Acme Plumbing"
"set up project for Acme Plumbing"
"show my pipeline"
```

## How It Works

- **Local SQLite database** at `~/.freelance-forge/pipeline.db` — auto-created on first use
- **Reports** saved as markdown files in `~/.freelance-forge/reports/`
- **No cloud services, no API keys, no subscriptions** — your data stays on your machine
- **Export to CSV or JSON** anytime for Notion, Google Sheets, or backup

## Requirements

- Python 3.8+
- An AI agent that supports SKILL.md files (OpenClaw, Claude Code, Codex CLI, etc.)
- `requests` and `beautifulsoup4` for web research (`pip install requests beautifulsoup4`)
- `playwright` (optional, for JS-rendered websites — `pip install playwright && playwright install chromium`)

## Directory Structure

```
~/.freelance-forge/
├── pipeline.db          # Your pipeline database
├── config.json          # Your preferences
├── shared/              # Python modules (auto-installed)
├── references/          # Templates (auto-installed)
├── reports/
│   ├── qualifications/  # Lead qualification reports
│   ├── proposals/       # Proposal documents
│   └── projects/        # Project briefs, checklists, sitemaps
└── exports/             # CSV/JSON exports
```

## License

See LICENSE file.
