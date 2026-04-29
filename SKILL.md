---
name: webclient-studio
description: Complete freelance web design pipeline — qualify leads, build proposals, onboard clients, and track your pipeline. Use when the user asks about managing freelance clients, qualifying leads, writing proposals, onboarding projects, or viewing their pipeline.
---

# WebClient Studio

A four-skill bundle for freelance web designers. Qualify leads, build proposals, onboard clients, and manage your entire pipeline through your AI agent. Everything runs locally — no cloud services, no API keys, no subscriptions.

## First Run

Before routing to any sub-skill, check if setup has been completed:

```bash
python3 -c "import sys,os; os.environ.get('WEBCLIENT_STUDIO_CONFIG_DIR') or exit(1); sys.path.insert(0, os.environ['WEBCLIENT_STUDIO_CONFIG_DIR']+'/shared'); import db_helper" 2>/dev/null && echo OK
```

- If `OK` — proceed to routing below.
- If it fails — read `references/setup.md` and execute the setup steps. Once setup completes, return here and proceed.

## Route Based on Intent

Read the user's message and determine which sub-skill to load. Then read that skill's SKILL.md and follow its instructions.

| User says | Load this skill |
|---|---|
| "qualify this lead" / "research this company" / "score this prospect" / "check out <URL>" | `skills/lead-qualifier/SKILL.md` |
| "build a proposal" / "write a proposal for <client>" / "create proposal from discovery notes" | `skills/proposal-builder/SKILL.md` |
| "set up project" / "onboard <client>" / "create project brief" / "generate checklist" | `skills/project-onboarder/SKILL.md` |
| "show my pipeline" / "update lead status" / "follow-ups" / "import CSV" / "export pipeline" / "add tag" / "show stats" | `skills/pipeline-tracker/SKILL.md` |

**Ambiguous intent:** If the user's message could match multiple skills (e.g. "tell me about Acme"), default to Pipeline Tracker — it's the command centre and can deep-dive into any lead's details.

**No match:** If nothing fits, ask the user what they'd like to do. Don't guess.

## How It Works

- **Local SQLite database** — auto-created on first use, stores at `$WEBCLIENT_STUDIO_CONFIG_DIR/pipeline.db`
- **Reports** — markdown files saved to `$WEBCLIENT_STUDIO_CONFIG_DIR/reports/`
- **Export** — CSV or JSON to `$WEBCLIENT_STUDIO_CONFIG_DIR/exports/`
- **Python 3.8+** required, plus `requests` and `beautifulsoup4` (installed during setup)
- **Playwright** optional but recommended for JS-rendered website research (installed during setup)

## Bundle Structure

```
webclient-studio/
├── SKILL.md                          ← You are here (entry point)
├── README.md                         ← Human-readable docs
├── skills/
│   ├── lead-qualifier/SKILL.md       ← Research & score leads
│   ├── proposal-builder/SKILL.md     ← Generate proposals
│   ├── project-onboarder/SKILL.md    ← Onboard new clients
│   └── pipeline-tracker/SKILL.md     ← Manage pipeline & export
├── shared/
│   ├── db_helper.py                  ← Pipeline database module
│   ├── web_research.py               ← Website crawling & extraction
│   └── templates.py                  ← Proposal & checklist templates
└── references/
    ├── setup.md                      ← First-run setup instructions
    ├── proposal-templates/           ← Proposal markdown templates
    ├── email-drafts/                 ← Email templates
    └── onboarding-checklists/        ← Onboarding checklists
```
