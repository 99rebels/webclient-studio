---
name: lead-qualifier
description: Research and score a prospective freelance web design client. Use when the user asks to qualify a lead, research a company, score a prospect, or check out a company at a URL. Produces a markdown qualification report and writes a summary row to the local pipeline database.
---

# Lead Qualifier

Research a prospective client, score them 1–10 as a fit for a freelance web designer, write an honest qualification report, and store a summary row in the pipeline database. This skill is the entry point of the Freelance Forge pipeline — every later skill (proposal, onboarding, tracking) reads what this skill writes.

## When to use this skill

Trigger phrases the user might say:
- "qualify this lead: <company or URL>"
- "research this company: <company or URL>"
- "score this prospect"
- "check out <company> for me"
- "I got an email from <company> — should I pursue this?"

If the user mentions a company by name *without* a URL, find the website first (web search). If you cannot find a website, ask the user for one or for a LinkedIn page. **Never proceed blind.**

## Tools

This skill uses CLI shims from the bundle's shared scripts. The shared scripts live at `$FREELANCE_FORGE_CONFIG_DIR/shared/` (default: `~/.freelance-forge/shared/`). Run shims with that directory on `PYTHONPATH`:

```bash
SHARED="${FREELANCE_FORGE_CONFIG_DIR:-$HOME/.freelance-forge}/shared"
PYTHONPATH="$SHARED" python3 -m db_helper <command>
PYTHONPATH="$SHARED" python3 -m web_research <url>
```

## First Run Check

Before the flow below, run the guard clause:
```bash
python3 -c "import sys; sys.path.insert(0, '$HOME/.freelance-forge/shared'); import db_helper" 2>/dev/null && echo OK
```

If `OK` — proceed to Flow.

If it fails — read `~/.freelance-forge/references/setup.md` and execute the setup steps. Once setup completes, return here and proceed with the Flow.

## Flow

### 1. Resolve the company to a website
- If the user gave a URL, use it.
- If only a name, search for the official website. Confirm the candidate URL with the user before proceeding (one line is fine: *"I found acmeplumbing.ie — is that the one?"*).
- If nothing findable, ask the user. Do not invent a URL.

### 2. Check for duplicates
```
python3 -m db_helper get-lead --company "<company name>"
```
If one or more matches return, present them and ask: *"Acme Plumbing already exists (status: qualified, score: 7). Update the existing entry, or create a new one?"* Don't silently overwrite.

### 3. Fetch and crawl
```
python3 -m web_research <url> --crawl
```
This fetches the given URL, then automatically discovers and crawls key business pages (contact, about, services, testimonials, pricing). It parses the site's sitemap if available, falls back to homepage link extraction, and caps at 5 additional pages by default.

Returns JSON with:
- `fetch.{accessible, source, status_code, notes}` — the homepage fetch result
- `crawl.{source, total_discovered, pages_crawled, audited_pages, not_crawled}` — what was discovered and what was crawled
- `extraction.{facts, tech_stack, social_links, contacts, suggested_tags, missing, pages_scanned}` — merged extraction across all pages

**Tell the user which pages were crawled and which were not.** Example: "Crawled 6 pages (homepage, contact, about, testimonials, and 2 others). 2 pages not crawled (faq, privacy policy)." The freelancer can manually review any skipped pages if the lead looks promising.

If `accessible` is false:
- The site is JS-rendered without Playwright, returned 4xx/5xx, or refused the request.
- Note this explicitly in the report. Set `research_quality=LOW`. Do **not** invent a description from the URL or domain name.

For single-page fetch (e.g., when the user links to a specific inner page and only wants that page checked), omit `--crawl`:
```
python3 -m web_research <url>
```

### 4. Optional: search and social
The web_research crawl covers the site's own pages. For external context, fall back to the agent's normal web search:
- `"<company> <location>"` — to find Google Business profile, reviews
- Look for LinkedIn / Facebook only if linked from the site or surfaced by search; do not go hunting

For each fact you add from search, **write down where it came from** (e.g. *"Google Business profile, 2026-04-26"*). The provenance ends up in the report's source annotations.

### 5. Score 1–10

Five factors per architecture (architecture / lead-qualifier §5.1):

| Factor | Weight | What it measures |
|---|---|---|
| Need Signal | High | Does their current site clearly need work? |
| Size Fit | High | Right size for a freelancer (not enterprise, not too small) |
| Budget Signal | Medium | Indicators they can afford professional web design |
| Accessibility | Medium | Can the freelancer reach the decision maker? |
| Timing Signal | Low | Are they looking for web services now? |

Honesty rules (lead-qualifier.md §5.3):
- The score stored in the database is a **single integer 1–10**.
- Nuance ("could be a 7 if budget signal confirmed") goes in the **Fit Assessment paragraph** of the report, not the database.
- If you genuinely lack info to score, store **NULL** — do not pick a number to fill the field. Explain in the report.
- Never inflate. A 5 is fine. Honest scores build trust.

### 6. Write the report

Save to:
```
$FREELANCE_FORGE_CONFIG_DIR/reports/qualifications/<company-slug>-<YYYY-MM-DD>.md
```
(default: `~/.freelance-forge/reports/qualifications/...`)

Use this exact structure (lead-qualifier.md §6.1):

```markdown
# Lead Qualification: <Company Name>

**Date:** <YYYY-MM-DD>
**Website:** <URL>
**Research Quality:** HIGH | MEDIUM | LOW

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
- <specific, evidence-based finding>
- ...

## Unverified / Could Not Confirm ⚠️

**Mandatory section. Never omit.**

Focus on findings that *should* have been verifiable but weren't. Skip universal unknowables (budget, internal decisions, timeline) — those are obvious.

- <claim that couldn't be confirmed> — <why> — <how the freelancer could verify>
- <assumption made> — <what it's based on> — <alternative interpretations>
- <data that should exist but doesn't> — e.g. "No Google Business profile found — unusual for a local business this size"

If everything was verified: "⚠️ All findings above were verified from public sources."

## Recommendation
2–3 sentences: what should the freelancer do with this lead, what angle to take.

## Suggested Next Steps
1. <action>
2. <action>
3. <action>
```

### 7. Write the database row

```
python3 -m db_helper add-lead "<Company Name>" \
    --website "<URL>" \
    --lead-score <integer or omit if NULL> \
    --research-quality HIGH|MEDIUM|LOW \
    --research-notes "<2–3 sentence summary, NOT the full report>" \
    --tags "wordpress,local-business,..."
```

Notes:
- The `research_notes` column is the **summary**, not the report. Keep it short.
- The shim auto-logs `lead_created` and `lead_scored` (if score given) in `activity_log`.
- Suggested tags from `web_research`'s `extraction.suggested_tags` are a starting point — add/remove to match what you actually saw.

### 8. Optional: first-contact email draft

Offer once: *"Want a first-contact email draft?"*

If yes, output **in chat only** (do not save). Rules (lead-qualifier.md §8):
- 3–5 sentences max
- Reference something specific from the research — not generic
- Suggest a concrete next step (discovery call, quick chat)
- Helpful and professional, never pushy
- **Never include the qualification score** — that's internal
- Never insult the prospect's current site
- No pricing

## Anti-hallucination rules (non-negotiable)

These come directly from `design-philosophy.md`. Every report must comply.

1. **Only report what was actually found.** Quote or closely paraphrase the source. Don't interpret and reframe.
2. **If you didn't find it, say so.** "Their CMS appears to be custom — could not confirm" is correct. "Their CMS is custom" without the qualifier is wrong.
3. **Don't extrapolate from limited data.** One contact form ≠ "lead generation focus." One review ≠ "customers are dissatisfied."
4. **Distinguish observation, inference, and hallucination.** Label inferences. Never include fabricated statistics.
5. **Use placeholders over fabrication.** "[Confirm with client: X]" is honest. A guess looks authoritative until it backfires.
6. **Numbers must be traceable.** Employee count, page count, load time, score — every number ties to a source.
7. **Verify names, URLs, contact details.** These are easy to verify and catastrophic to get wrong.
8. **Confidence levels on key claims.** HIGH = direct from their own site. MEDIUM = third-party (search, reviews). LOW = inferred from indirect evidence.

## Edge cases

| Scenario | Action |
|---|---|
| Company name only, no website found | Search for it. Still nothing → ask the user. Don't proceed without a URL or LinkedIn. |
| Site is down / unreachable | Note in report. Try cached version or social. Flag as data quality issue. `research_quality=LOW`. |
| Multiple companies with similar names | Present options, ask user to confirm. Don't guess. |
| Clearly enterprise (500+ employees) | Still produce report. Note: likely has in-house team or agency — different approach needed. |
| Very small (micro-business) | Still produce report. Note: budget likely limited. |
| LOW research quality | Heavy uncertainty flags. Recommend manual research before contact. Don't inflate score because of missing contrary evidence. |
| Different country | Note location, timezone, language, payment implications. Don't disqualify on location alone. |
| Already exists in pipeline | Step 2 already handles this — present options. |
| Config file missing | Auto-created by `db_helper` on first call. No setup step. |

## End-of-turn

Tell the user: report path, lead ID, score, and any tags applied. Offer the optional email draft.

Example end-of-turn line:
> Wrote `~/.freelance-forge/reports/qualifications/acme-plumbing-2026-04-26.md` (score 7/10, MEDIUM research quality, tags: wordpress, local-business). Want a first-contact email draft?
