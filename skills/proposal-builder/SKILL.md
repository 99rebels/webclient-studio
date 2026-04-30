---
name: proposal-builder
description: Build a scoped freelance web design proposal from discovery call notes. Use when the user wants to write or generate a proposal, build a proposal from discovery, or create a proposal for a client already in the pipeline. Produces a markdown proposal document and updates the pipeline row.
---

# 📝 Proposal Builder

Take discovery call notes plus the lead's existing research, and produce a scoped, professional proposal the client can say yes to. Save as markdown and update the pipeline status to `proposal_sent`.

## When to use

- "build a proposal for <client>"
- "write a proposal from our discovery call"
- "create proposal for <client>"
- "I just finished a call with <client>" → offer to build the proposal
- "they want <services>" → start with scope hints

## ⚡ Tools

```bash
SHARED="$WEBCLIENT_STUDIO_CONFIG_DIR/shared"
PYTHONPATH="$SHARED" python3 -m db_helper <command>
PYTHONPATH="$SHARED" python3 -m templates render <path> --json '...'
```

**⚠️ Path expansion in JSON:** The shell does not expand variables inside single quotes. Always expand before inserting:

```bash
# ❌ Wrong — $VAR stored as literal
python3 -m db_helper update-field <id> '{"path": "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/foo"}'

# ✅ Right — variable expands first
CLIENT_DIR="$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/acme"
python3 -m db_helper update-field <id> '{"path": "'"$CLIENT_DIR"'"}'
```

## Guard clause

Before the flow, run:

```bash
python3 -c "import sys,os; os.environ.get('WEBCLIENT_STUDIO_CONFIG_DIR') or exit(1); sys.path.insert(0, os.environ['WEBCLIENT_STUDIO_CONFIG_DIR']+'/shared'); import db_helper" 2>/dev/null && echo OK
```

- **OK** → set `SHARED="$WEBCLIENT_STUDIO_CONFIG_DIR/shared"` and proceed. All `python3 -m` commands assume `PYTHONPATH="$SHARED"`.
- **Fails** → read `$WEBCLIENT_STUDIO_CONFIG_DIR/references/setup.md` (or bundle's `references/setup.md`), execute setup, then return here.

## 🔄 Flow

### 1. Find the client in the pipeline

```bash
python3 -m db_helper get-lead --company "<client name>"
```

| Result | Action |
|---|---|
| One match | Continue with that lead row |
| Multiple matches | Present with id, status, score. Ask user to pick |
| No match | Check for a qualification report (below) |

**No match — check for qualification report:**

```bash
ls "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/qualifications/*<client-slug>* 2>/dev/null
ls "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/clients/<client-slug>/<client-slug>* 2>/dev/null
```

**If a report exists:** Auto-add the lead silently. Capture the actual filename from the glob, extract score/confidence/summary from the report, create client folder, move report, store paths:

```bash
mkdir -p "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<client-slug>"
mv "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/qualifications/*<client-slug>* \
   "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/clients/<client-slug>/

python3 -m db_helper add-lead "<Company Name>" \
    --website "<URL from report>" \
    --lead-score <score from report> \
    --data-confidence <from report> \
    --research-notes "<summary from report>" \
    --pitch-notes "<pros/cons extracted from report>" \
    --tags "<from report>" \
    --client-dir-path "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<client-slug>" \
    --qualification-report-path "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<client-slug>/<actual-filename>"
```

Then continue to Step 2.

**No report either:** Offer:
1. Run Lead Qualifier first (recommended — better proposal context)
2. Create a minimal lead row now and proceed
3. Cancel

### 2. Get discovery notes

If already pasted, use them. If not, ask: *"Paste your discovery notes — or want me to generate a discovery call template first?"*

If template: output a structured question list in chat (not a file): goals, audience, features, timeline, budget signal, content readiness, brand preferences, technical requirements. Once they have notes, restart.

**Never invent discovery content.** If notes are too thin, build a minimal proposal with `[Confirm with client: ...]` placeholders.

### 3. Read the lead row and qualification report

```bash
python3 -m db_helper get-lead --id <lead-id>
python3 -m db_helper tag list --lead-id <lead-id>
```

Check the row for `qualification_report_path`:

```
Path exists  → Read the full qualification report. Use detailed findings
               (tech stack, contacts, website quality, unverified items)
               to inform scope, positioning, and pricing.

Path is null  → Fall back to DB summary (research_notes, lead_score, tags).
               Less specific but still functional.
```

Combine: qualification report (or summary) + tags + lead score + discovery notes.

### 4. First-run pricing strategy check

```bash
python3 -m db_helper config get
```

If `preferences.pricingStrategy` is null, ask the user **once**:

> "Do you have a pricing strategy you'd like me to use? Options: `day_rate`, `project_based`, `value_based`, `tiered`, or skip (use market-informed ranges)."

Persist their choice:
```bash
python3 -m db_helper config set --path preferences.pricingStrategy --value '"day_rate"'
```

Use `null` for "skip / use market ranges". **Don't ask again.**

### 5. Render and adapt the proposal

```bash
python3 -m templates render proposal-templates/default.md \
    --json-file /tmp/ctx.json \
    --out "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<slug>/<slug>-<YYYY-MM-DD>-proposal.md"
```

The template is a **starting point**, not a form. After rendering, **read and adapt** the file:
- Reference specific things from discovery notes
- Use the client's language ("booking system" not "appointment scheduling module")
- Mark gaps as `[Confirm with client: <specific thing>]` — never fabricate

### 6. Pricing

Pricing is the most sensitive section. The agent provides context and structure, not the final price.

```
✅ Present ranges:    "£2,000–£3,500 for a 6-page responsive site with CMS"
❌ Never fixed price:  "£2,750"
```

- Ranges informed by: service type, scope, budget signal from research, regional market
- Always flag: *"Final price is yours to set based on your rate, experience, and the relationship."*
- If `pricingStrategy` is set, frame in that style (day rate × days, project phases, tiered packages)
- If no pricing signal at all: wide range + *"Recommend clarifying scope before finalising."*

### 7. Tone and style

Write in the freelancer's voice (first person or first plural). Confident, not arrogant. Short scannable paragraphs. **Avoid superlatives** ("revolutionary", "game-changing"). No jargon the client won't understand.

### 8. Required structure

The template ships with these sections — keep this order:

```
1. Executive Summary   (2–3 paragraphs)
   What they do, why this project matters, what the proposal covers

2. Scope of Work       Specific deliverables, what's included/excluded, assumptions

3. Timeline            Phases, milestones, dates as estimates

4. Investment          (not "Price" or "Cost")
   Broken down, ranges, payment schedule

5. Terms & Conditions  Revisions, payment, cancellation, IP transfer
   Note: "outline, not legal contract"

6. Next Steps          What happens if they say yes, how to respond, suggested date
```

### 9. Update the database

```bash
python3 -m db_helper update-field <lead-id> \
    '{"proposal_summary": "<2-3 sentence summary, NOT the full proposal>", "proposal_date": "<YYYY-MM-DD>", "proposal_report_path": "<path to proposal file>"}'

python3 -m db_helper update-status <lead-id> proposal_sent
```

The shim auto-logs `proposal_created` and `status_changed`. If discovery notes captured separately:

```bash
python3 -m db_helper update-field <lead-id> \
    '{"discovery_notes": "<concise notes, not full transcript>"}'
```

### 10. Optional: covering email draft

Offer once: *"Want a covering email draft for the proposal?"*

If yes, read the full proposal first (if not already in context):

```bash
python3 -m db_helper get-lead --company "<company>"
```

Read the file at the `proposal_report_path` field from the result. Use the full proposal to write a personalised summary. If the path is null, fall back to `proposal_summary` from the DB.

Output **in chat only**. Rules:
- Reference the discovery call positively
- 2–3 sentence summary of what the proposal covers
- Clear call to action
- Brief — the proposal does the heavy lifting
- **Never include the price in the email**
- **Do not use generic template language** — reference specific scope items, page names, features, or timeline from the actual proposal. The client should feel like you wrote this email for them, not pulled it from a template.

## Edge cases

```
Brief discovery notes       → Minimal proposal with placeholders. Suggest follow-up call.
Discovery contradicts research → Trust discovery (more recent, direct from client).
No research on lead row     → Use discovery notes alone. Less tailored, functional.
Proposal already exists     → Alert user. Offer new version vs update existing.
Out-of-scope features       → Include as "future phase" or "not in current scope".
Can't deliver requested     → Include with [Verify capability: ...] flag.
Skip pricing strategy       → Persist null. Use market ranges. Don't ask again.
```

## End-of-turn

Tell the user: file path, status now `proposal_sent`, summary of what was included, any `[Confirm with client: ...]` placeholders. Offer the covering email.

```
"Written to $WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/acme-plumbing/acme-plumbing-2026-04-26-proposal.md. Status → proposal_sent. 2 placeholders to confirm with client (booking system features, content deadline). Want a covering email draft?"
```

## Notes

- **Format output** for the current channel — adapt formatting to match what the platform supports
- **Cross-skill data contract:**
  - **Reads** from Lead Qualifier: `qualification_report_path`, `research_notes`, `lead_score`, `tags`, `data_confidence`
  - **Writes** for Pipeline Tracker: `proposal_summary`, `proposal_date`, `proposal_report_path`, `discovery_notes`
  - **Writes** for Project Onboarder: `discovery_notes`
- **Template location:** `proposal-templates/default.md` (relative to bundle root)
