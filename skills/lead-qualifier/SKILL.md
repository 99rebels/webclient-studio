---
name: lead-qualifier
description: Research and score a prospective freelance web design client. Use when the user asks to qualify a lead, research a company, score a prospect, or check out a company at a URL. Produces a markdown qualification report and writes a summary row to the local pipeline database.
---

# 🔍 Lead Qualifier

Research a prospective client, score them 1–10, write an honest qualification report, and store a summary row in the pipeline database. This is the **entry point** of the WebClient Studio pipeline — every later skill (proposal, onboarding, tracking) reads what this skill writes.

## Why

Freelance web designers waste hours researching leads that go nowhere. This skill crawls the prospect's site, extracts what matters, scores the fit, writes a report, and stores it in the pipeline so every downstream skill can use it.

## When to use

- "qualify this lead: <company or URL>"
- "research this company: <company or URL>"
- "score this prospect"
- "check out <company> for me"
- "I got an email from <company> — should I pursue this?"
- "add [company] to my pipeline" → jump to **Add from existing report** (below)

If the user gives a name without a URL, find the website first. **Never proceed without a URL or LinkedIn.**

## ⚡ Tools

This skill uses the bundle's shared Python modules. Set `SHARED` to the shared scripts directory:

```bash
SHARED="$WEBCLIENT_STUDIO_CONFIG_DIR/shared"
PYTHONPATH="$SHARED" python3 -m db_helper <command>
PYTHONPATH="$SHARED" python3 -m web_research <url>
```

**⚠️ Path expansion in JSON:** The shell does not expand variables inside single quotes. Always expand paths before inserting into JSON:

```bash
# ❌ Wrong — $VAR stored as literal string
python3 -m db_helper update-field <id> '{"path": "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/foo"}'

# ✅ Right — variable expands before JSON is built
CLIENT_DIR="$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/acme"
python3 -m db_helper update-field <id> '{"path": "'"$CLIENT_DIR"'"}'
```

## Guard clause

Before the flow, run:

```bash
python3 -c "import sys,os; os.environ.get('WEBCLIENT_STUDIO_CONFIG_DIR') or exit(1); sys.path.insert(0, os.environ['WEBCLIENT_STUDIO_CONFIG_DIR']+'/shared'); import db_helper" 2>/dev/null && echo OK
```

- **OK** → set `SHARED="$WEBCLIENT_STUDIO_CONFIG_DIR/shared"` and proceed to Flow. All `python3 -m` commands in the flow assume `PYTHONPATH="$SHARED"` is set.
- **Fails** → read `$WEBCLIENT_STUDIO_CONFIG_DIR/references/setup.md` (or the bundle's `references/setup.md`), execute setup, then return here.

## 🔄 Flow

### 1. Resolve to a website

Use the URL if provided. If only a name, search for the official site and confirm: *"I found acmeplumbing.ie — is that the one?"*

If nothing findable, ask the user. Do not invent a URL.

### 2. Check for existing leads

```bash
python3 -m db_helper get-lead --company "<company name>"
python3 -m db_helper tag list --lead-id <id>   # if match found
```

| Match | Action |
|---|---|
| No match | Proceed to Step 3 (normal flow) |
| Match with `imported` tag | Switch to **Enrichment Mode** (below) |
| Match without `imported` tag | If status is `lead` (no qualification yet): run Steps 3–6 (fetch, score, write report). Then create the client folder, move the report, update the existing row with all fields including paths, and set status to `qualified`. Follow the same pattern as Enrichment Mode (mkdir, mv, update-field for paths, update-status qualified). If status is anything else: ask: "Acme Plumbing already exists (status: X, score: Y). Update or create new?" Don't silently overwrite. |

#### Enrichment Mode (imported leads)

Imported leads are already in the pipeline — the user decided to pursue them. Qualification *verifies* that decision.

1. Run Steps 3–6 as normal (fetch, crawl, score, write report).
2. Create the client folder and move the report:
   ```bash
   mkdir -p "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<company-slug>"
   mv "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/qualifications/<company-slug>-<YYYY-MM-DD>.md" \
      "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<company-slug>/"
   ```
3. Update the existing row (don't create new):
   ```bash
   python3 -m db_helper update-field <lead-id> '{"lead_score": <score>, "data_confidence": "<confidence>", "research_notes": "<summary>", "pitch_notes": "<pros/cons>", "website": "<URL>"}'
   python3 -m db_helper update-field <lead-id> '{"client_dir_path": "<path>", "qualification_report_path": "<path>"}'
   ```
4. Remove `imported` tag: `python3 -m db_helper tag remove --lead-id <id> --name imported`
5. Add any new tags from qualification research: `python3 -m db_helper tag add --lead-id <id> --name <tag>`
6. Update status to `qualified`: `python3 -m db_helper update-status <lead-id> qualified`
7. Tell the user: *"Acme Plumbing updated: score NULL → 7, confidence LOW → HIGH. Imported tag removed — fully qualified."* Offer the email draft.

### 3. Fetch and crawl

```bash
python3 -m web_research <url> --crawl
```

Fetches the URL, discovers and crawls key pages (contact, about, services, testimonials, pricing). Parses sitemap if available, falls back to homepage links, caps at 5 additional pages.

Returns JSON:
```
fetch.{accessible, source, status_code, notes}
crawl.{source, total_discovered, pages_crawled, audited_pages, not_crawled}
extraction.{facts, tech_stack, social_links, contacts, suggested_tags, missing, pages_scanned}
```

**Tell the user what was crawled and what wasn't.** Example: "Crawled 6 pages (homepage, contact, about, testimonials, +2). 2 skipped (faq, privacy policy)."

If `accessible` is false — site is JS-rendered without Playwright, returned 4xx/5xx, or refused. Set `data_confidence=LOW`. Do **not** invent content. See `references/edge-cases.md` for additional handling (cached versions, social fallback).

For single-page fetch, omit `--crawl`:
```bash
python3 -m web_research <url>
```

### 4. External search (optional)

For context beyond the company's site, use `web_search`:
- `"<company> <location>"` — Google Business profile, reviews
- LinkedIn/Facebook only if surfaced by search — don't hunt

**Note the source** for every external fact: *"Google Business profile, 2026-04-26"*

### 5. Score 1–10

```
🔴 HIGH    → Need Signal    Does their site clearly need work?
🔴 HIGH    → Size Fit       Right size for a freelancer?
🟡 MEDIUM  → Budget Signal  Can they afford professional web design?
🟡 MEDIUM  → Accessibility  Can the freelancer reach the decision maker?
🟢 LOW     → Timing Signal  Are they looking for web services now?
```

**Honesty rules:**
- Single integer 1–10 stored in DB. Nuance goes in the report, not the score.
- If you can't score, store **NULL** — don't guess. Explain in the report.
- Never inflate. A 5 is fine. Honest scores build trust.

### 6. Write the report

Save to `$WEBCLIENT_STUDIO_CONFIG_DIR/reports/qualifications/<company-slug>-<YYYY-MM-DD>.md`

**Keep this flat location for the initial save.** When added to pipeline (Step 7a), the report moves to the client folder. The two-step process means the report exists even if the freelancer decides not to add the lead.

Report structure:

```markdown
# Lead Qualification: <Company Name>

**Date:** <YYYY-MM-DD>
**Website:** <URL>
**Data Confidence:** HIGH | MEDIUM | LOW

---

## Company Overview
2–4 paragraphs. What they do, where they are, how big they are, current market position. Coherent prose, not bullet points.

## Current Web Presence
**Website:** <URL>
**Platform:** <WordPress | Wix | Custom | Unknown>
**Quality Assessment:** <brief assessment>

Key observations about their current site.

## Fit Assessment
**Score:** <X/10> (or "NULL — insufficient information to score")
**Verdict:** STRONG | GOOD | MODERATE | WEAK

**Reasoning:**
- Need Signal: <evidence>
- Size Fit: <evidence>
- Budget Signal: <evidence>
- Accessibility: <evidence>
- Timing Signal: <evidence>

## Key Findings
- <specific, evidence-based finding>
- ...

## Unverified / Could Not Confirm ⚠️

**Mandatory section. Never omit.**

Focus on findings that *should* have been verifiable but weren't. Skip universal unknowables (budget, internal decisions, timeline).

- <claim> — <why> — <how to verify>
- <assumption> — <what it's based on> — <alternative interpretations>

If all verified: "⚠️ All findings above were verified from public sources."

## Recommendation
2–3 sentences: what to do, what angle to take.

## Suggested Next Steps
1. <action>
2. <action>
3. <action>
```

### 7. Ask before adding to pipeline

Show the user: **Score** (X/10 or NULL), **Verdict** (STRONG/GOOD/MODERATE/WEAK), **One-line summary**.

Ask: "Add to pipeline?"

- **Yes** → Step 7a.
- **No / maybe later** → stop. Report is saved — they can add it anytime (see "Add from existing report" below).

### 7a. Create client folder and write database row

```bash
mkdir -p "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<company-slug>"
mv "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/qualifications/<company-slug>-<YYYY-MM-DD>.md" \
   "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<company-slug>/"
```

Write the row. **Read the saved report file** to extract values — do NOT rely on conversation memory.

```bash
python3 -m db_helper add-lead "<Company Name>" \
    --website "<URL>" \
    --lead-score <integer from report, or omit if NULL> \
    --data-confidence <from report> \
    --research-notes "<2–3 sentence summary from Fit Assessment + Recommendation>" \
    --pitch-notes "<pros/cons from findings>" \
    --tags "<from report>" \
    --client-dir-path "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<company-slug>" \
    --qualification-report-path "$WEBCLIENT_STUDIO_CONFIG_DIR/reports/clients/<company-slug>/<company-slug>-<YYYY-MM-DD>.md"

python3 -m db_helper update-status <lead-id> qualified
```

The lead enters the pipeline as `qualified` — it was scored and the user consciously added it.

Key field details:

```
research_notes  → Summary (not the report). From Fit Assessment + Recommendation.
lead_score      → From report's "Score:" line. Integer or omit for NULL.
pitch_notes     → Pros/cons list from the freelancer's perspective:
                   **Pros:** <why pitch — work needed, right size, clear angle>
                   **Cons:** <why skip — too small, wrong location, no timing signal>
                   Pick the most impactful 2-4 each. Don't list everything.
tags            → From findings (tech stack, business type, notable characteristics).
                   web_research's suggested_tags are a starting point — adjust.
client_dir_path           → All future reports (proposal, onboarding) go here.
qualification_report_path → Proposal Builder reads this to inform the proposal.
```

The shim auto-logs `lead_created` and `lead_scored` in `activity_log`.

### Add from existing report

When the freelancer says "add [company] to my pipeline":

1. **Check pipeline first:**
   ```bash
   python3 -m db_helper get-lead --company "<Company Name>"
   ```
   If exists: tell user and offer to show/update.

2. **Check for a qualification report:**
   ```bash
   ls "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/qualifications/*<company-slug>* 2>/dev/null
   ls "$WEBCLIENT_STUDIO_CONFIG_DIR"/reports/clients/<company-slug>/<company-slug>* 2>/dev/null
   ```
   If found: read report, extract values, run `add-lead` from Step 7a.

3. If no report: "No qualification report found for [company]. Run Lead Qualifier first to create one, or provide details to add manually."

Works across sessions — the report file is the source of truth, not conversation memory.

### 8. Email draft + talking points

Offer once: *"Want a first-contact email draft?"*

If yes, read the full qualification report first (if not already in context from this session):

```bash
python3 -m db_helper get-lead --company "<company>"
```

Read the file at the `qualification_report_path` field from the result. Use the **full report** — not the DB summary — for the email draft and talking points. The report contains the specific findings, tech stack, and observations needed to write a personalised email.

If `qualification_report_path` is null, fall back to `research_notes` from the DB. The email will be less specific but still functional.

Output **in chat only** (do not save).

**Draft email:** 3–5 sentences, reference specific research, suggest a next step, professional tone, no score, no pricing, never insult their current site. **Do not use generic template language** — every sentence should reference something specific from the report (their actual tech stack, a real page you found, a concrete issue, their industry, their size). Two emails for different clients must read like two different people wrote them.

**Talking points** (always include):

```
Angle:         <one-line approach>
Pain points:   <2-3 concrete issues found>
Key fact:      <most noteworthy positive thing>
Suggested opener: <how to introduce yourself>
Call to action:   <quick chat, phone call, free audit>
Things to avoid:  <what would land wrong>
```

## 🔒 Anti-hallucination rules

Non-negotiable. Every report must comply.

1. **Only report what was actually found.** Quote or closely paraphrase.
2. **If you didn't find it, say so.** "Appears to be custom — could not confirm" is correct.
3. **Don't extrapolate from limited data.** One form ≠ "lead generation focus."
4. **Distinguish observation, inference, and hallucination.** Label inferences.
5. **Use placeholders over fabrication.** "[Confirm with client: X]" is honest.
6. **Numbers must be traceable.** Every number ties to a source.
7. **Verify names, URLs, contact details.** Easy to verify, catastrophic to get wrong.
8. **Confidence levels on key claims.** HIGH = their own site. MEDIUM = third-party. LOW = inferred.

## End-of-turn

**If added to pipeline:** tell the user lead ID, score, and tags. Offer the email draft.

**If not added:** tell the user the report path. Remind them they can add it anytime.

```
✅ "Added Acme Plumbing to pipeline (score 7/10, tags: wordpress, local-business). Want a first-contact email draft?"

❌ "Report saved at $WEBCLIENT_STUDIO_CONFIG_DIR/reports/qualifications/acme-plumbing-2026-04-26.md. Add it anytime — just say 'add Acme Plumbing'."
```

## Notes

- **Edge cases** — see `references/edge-cases.md` (dead sites, enterprise leads, international prospects, micro-businesses)
- **Format output** for the current channel — adapt formatting to match what the platform supports
- **Cross-skill data contract:** downstream skills read these database fields:
  - `qualification_report_path` → Proposal Builder, Project Onboarder
  - `lead_score` → Pipeline Tracker (sort by score)
  - `research_notes`, `tags`, `data_confidence` → all downstream skills
