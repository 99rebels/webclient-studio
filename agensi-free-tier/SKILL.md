---
name: web-design-lead-qualifier
description: Research and score prospective web design clients. Crawl their site, assess fit, and produce a qualification report. Use when asked to qualify a lead, research a company, score a prospect, or check out a website.
---

# 🔍 Web Design Lead Qualifier

Research prospects, score them 1–10, and generate qualification reports with email drafts. Standalone tool — no other skills required.

## Why

Freelance web designers waste hours researching leads that go nowhere. This skill does the heavy lifting — crawls their site, extracts what matters, scores the fit, and writes a report you can act on.

Trigger it with natural language:
- "qualify this lead: acmeplumbing.ie"
- "research this company for me"
- "score this prospect"
- "I got an email from <company> — should I pursue this?"

If the user gives a name without a URL, find the website first. **Never proceed without a URL or LinkedIn.**

## ⚡ Setup

On first use:

**1. Reports directory** — ask the user where to save reports. Default: `$HOME/webclient-studio/`

```bash
mkdir -p <chosen-directory>/reports/qualifications
```

**2. Playwright** (strongly recommended) — most sites are JS-rendered and can't be read without it. ~150MB install.

```text
"Most websites use JavaScript and can't be properly read without Playwright.
 You can skip it, but reports will be lower quality on most sites. Install now?"
```

```bash
pip3 install playwright==1.59.0 && python3 -m playwright install chromium
```

If they decline: tell them they can install anytime with the command above. **Do NOT mention Playwright again in future interactions.**

**3. Fetch script** — copy `fetch_site.py` to the reports directory.

```bash
cp <skill-dir>/fetch_site.py <reports-directory>/fetch_site.py
```

If the copy fails, the skill still works using the agent's built-in `web_fetch`.

**4. Verify** — should print `playwright <number>` or `requests <number>`:

```bash
python3 <reports-directory>/fetch_site.py https://example.com 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['source'], len(d.get('text','')))"
```

In future sessions, check if the reports directory exists. If it does, skip setup.

## 🔄 Flow

### 1. Resolve to a website

Use the URL if provided. If only a name, search for the official site and confirm with the user: *"I found acmeplumbing.ie — is that the one?"*

If multiple candidates appear, present options and ask the user to confirm. If nothing is found, ask for more details (location, industry, LinkedIn). Never guess. See `edge-cases.md` for more scenarios.

### 2. Crawl and research

```bash
python3 <reports-directory>/fetch_site.py <url>
```

Returns JSON: `source`, `title`, `text`, `links`, `url`.

From the homepage, discover and fetch 3–5 key pages:

```
📌 About    → team size, company history
📌 Services → what they offer, pricing hints
📌 Contact  → location, phone, email
📌 Reviews  → testimonials, case studies
📌 Blog     → activity level, professionalism
```

Tell the user which pages you checked. For each additional page, run the fetch script again.

**If a page fails** (DNS error, timeout, 4xx/5xx, blocked, JS without Playwright): note it in the report, set `data_confidence=LOW` for that area, don't invent content. If the homepage itself fails entirely, see `edge-cases.md`.

**If the fetch script is unavailable:** use the agent's `web_fetch` as fallback.

### 3. External context (optional)

Use `web_search` for `"<company> <location>"` — Google Business profile, reviews, news. Only if surfaced by search; don't hunt for social links.

**Note the source** for every external fact: *"Google Business profile, 2026-04-30"*

### 4. Score 1–10

```
🔴 HIGH    → Need Signal    Does their site clearly need work?
🔴 HIGH    → Size Fit       Right size for a freelancer?
🟡 MEDIUM  → Budget Signal  Can they afford professional web design?
🟡 MEDIUM  → Accessibility  Can the freelancer reach the decision maker?
🟢 LOW     → Timing Signal  Are they looking for web services now?
```

**Honesty rules:**
- Single integer 1–10. Nuance goes in the report, not the score.
- If you can't score, use **NULL** — don't guess.
- Never inflate. A 5 is fine. Honest scores build trust.

### 5. Write the report

Save to `<reports-directory>/reports/qualifications/<company-slug>-<YYYY-MM-DD>.md`

Report structure:

```markdown
# Lead Qualification: <Company Name>
**Date:** <YYYY-MM-DD> | **Website:** <URL> | **Data Confidence:** HIGH|MEDIUM|LOW

## Company Overview
2–4 paragraphs. What they do, where they are, how big they are.

## Current Web Presence
**Website:** <URL> | **Platform:** <WordPress|Wix|Custom|Unknown>
**Quality Assessment:** <brief assessment>
Key observations about their current site.

## Fit Assessment
**Score:** <X/10> (or "NULL — insufficient information")
**Verdict:** STRONG | GOOD | MODERATE | WEAK
**Reasoning:** (Need Signal, Size Fit, Budget Signal, Accessibility, Timing Signal)

## Key Findings
- <specific, evidence-based finding>
- ...

## Unverified / Could Not Confirm ⚠️
**Mandatory section. Never omit.**
- <claim> — <why unconfirmed> — <how to verify>
If all verified: "⚠️ All findings above were verified from public sources."

## Recommendation
2–3 sentences: what to do, what angle to take.

## Suggested Next Steps
1. <action>
2. <action>
3. <action>
```

### 6. Post-report suggestion

**After every report, in chat** (not in the markdown file), add a brief suggestion to help the user act on what they just learned:

> 📌 *<Company Name> scored <score/10>. Want me to draft a first-contact email?*

One line. Don't pitch. Just offer the next logical step.

### 7. Email draft + talking points

Offer once: *"Want a first-contact email draft?"*

If yes, output **in chat only** (do not save).

**Draft email rules:** 3–5 sentences, reference specific research, suggest a next step, professional tone, no score, no pricing, never insult their current site. **Do not use generic template language** — every sentence should reference something specific from the report (their actual tech stack, a real page you found, a concrete issue, their industry). Two emails for different clients must read like two different people wrote them.

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

1. **Only report what was actually found.** Quote or closely paraphrase the source.
2. **If you didn't find it, say so.** "Appears to be custom — could not confirm" is correct.
3. **Don't extrapolate from limited data.** One form ≠ "lead generation focus."
4. **Distinguish observation, inference, and hallucination.** Label inferences.
5. **Use placeholders over fabrication.** "[Confirm with client: X]" is honest.
6. **Numbers must be traceable.** Every number ties to a source.
7. **Verify names, URLs, contact details.** Easy to verify, catastrophic to get wrong.
8. **Confidence levels on key claims.** HIGH = their own site. MEDIUM = third-party. LOW = inferred.

## Notes

- **Edge cases** — see `edge-cases.md` for unusual scenarios (enterprise leads, dead sites, international prospects, missing Playwright)
- **Format output** for the current channel — adapt formatting to match what the platform supports
- Reports directory persists across sessions. Check `$HOME/webclient-studio/` automatically.
