# Internal Teardown: WebClient Studio

**Format:** Teardown (internal — not for publication)
**Date:** 28 April 2026
**Reviewer:** Cambrian
**Bundle version:** Single-commit repo (eb69751), no version tag
**Price point evaluated against:** $19 one-time

---

## Claim Surface

The bundle makes these claims (all from the README):

1. **"Zero setup. No API keys. No external services."** — Everything runs locally.
2. **Four-skill bundle** covering the full pre-build workflow: lead qualification → proposal generation → project onboarding → pipeline management.
3. **"Zero API keys, zero external services, zero configuration"** — your data stays on your machine.
4. **"Designed for web freelancers"** who want to automate the pre-build process.
5. **"Works with OpenClaw, Claude Code, Codex CLI, and Cursor"** — any agent with file system access.
6. One-command install: `./install.sh`.

---

## Verdict: Install with Caveats

The bundle clears the bar for a Stack Play subject. The two core Python modules (db_helper.py and web_research.py) are genuinely well-built. The SKILL.md architecture is thoughtful and thorough. The "specifies what it could not verify" claim is architecturally real, though it has an implementation bug that undermines it in practice. At $19 one-time, the pricing is fair for what the bundle delivers.

But seven specific issues need fixing before a Stack Play can fairly cover it. None are dealbreakers, but several are public-claim failures or implementation bugs that would surface in honest testing.

---

## The Evidence Base

### File Inventory

| Category | Files | Lines |
|---|---|---|
| Python (shared/) | 4 (db_helper.py, web_research.py, templates.py, \_\_init\_\_.py) | 1,785 |
| SKILL.md (skills/) | 4 | 1,108 |
| Design docs (subskills/) | 4 | 1,194 |
| Architecture docs | 3 (architecture.md, storage.md, design-philosophy.md) | 1,275 |
| Reference templates | 6 (1 proposal, 1 checklist, 4 email drafts) | 246 |
| Setup docs | 1 (references/setup.md) | 184 |
| README | 1 | 73 |
| **Total** | **27 files** (excl. .git) | **~5,865** |

Languages: Python (1,785 lines), Markdown (4,080 lines), no shell scripts.

### What's Not in the Repo

- **No install.sh or install.ps1.** The README line 20 says `./install.sh`. Neither file exists. This is a public-claim failure — the README describes a one-command install that doesn't exist.
- **No tests.** Zero test files, no test framework, no CI.
- **No requirements.txt or pyproject.toml.** Dependencies are listed in the README and setup.md but not in a machine-readable format.
- **No LICENSE file.**
- **No CHANGELOG or VERSION file.**

---

## Code Review: Security

**Clean bill.** No ClawHavoc-class issues found.

| Check | Result |
|---|---|
| External network calls to unexpected hosts | None. web_research.py only connects to the URL the user provides. No telemetry, no phone-home. |
| Credential access | None. No `.env` reading, no token access, no browser cookie access, no keychain access. |
| File system scope | Confined to `~/.webclient-studio/` for data storage. Shared scripts read from the install location. No writes outside these boundaries. |
| Obfuscation | None. All code is plain, readable Python. |
| Companion skill installation | None. No skill installs other skills or modifies the agent's configuration. |
| SQL injection | Uses parameterised queries throughout db_helper.py. No raw SQL string interpolation. |

---

## Code Review: db_helper.py (967 lines)

**Assessment: Solid.** This is the strongest piece of code in the bundle.

**What's good:**
- Clean separation: wrapper functions for every operation, each with activity logging enforced at the wrapper level (callers can't skip it).
- Transaction handling is correct: `BEGIN`/`COMMIT`/`ROLLBACK` in a context manager pattern.
- `update_lead_status` correctly updates `status_since` and `date_updated`.
- `record_follow_up` correctly does NOT touch `status_since` (preserves the original status start date).
- `get_stale_leads` uses `MAX(status_since, last_follow_up)` — correct logic for detecting leads that need follow-up regardless of how they entered the current status.
- Dry-run support (`--dry-run`) on all write functions.
- Fuzzy matching via `ILIKE` for company name search.
- UUID primary keys, ISO 8601 timestamps, proper foreign keys with `ON DELETE CASCADE`.
- Export to both CSV and JSON.
- Config management with dot-notation paths (e.g., `preferences.pricingStrategy`).
- Comprehensive CLI shim covering every function.

**What's not ideal:**
- The `update-field` command uses a positional argument named `json` (line ~690 of argparse). Users and agents naturally type `--json`, which causes a silent error. The SKILL.md correctly documents it as positional, but this is a usability footgun that will bite people. An optional `--json` flag alongside the positional would solve this.
- `data_confidence` column in the leads table is documented as `HIGH/MEDIUM/LOW` in the SKILL.md but is a free-text field in the schema (no CHECK constraint). An agent could store anything.
- No input validation on lead scores — the CLI accepts any integer, including negative numbers or values above 10. The SKILL.md says 1-10, but the code doesn't enforce it.

**Scale test:** 24 leads in the database. Pipeline query (grouped by status, sorted by score within groups) returned in **0.030 seconds**. No performance concerns at this scale. SQLite will handle hundreds of leads without issue; performance would degrade around 10,000+ leads with complex joins, but that's far beyond a solo freelancer's use case.

---

## Code Review: web_research.py (655 lines)

**Assessment: Good architecture, noisy extraction, one merge bug.**

### What's good

- **Playwright-first / HTTP-fallback pattern** is exactly right for freelancer use cases. Most small business sites are WordPress (server-rendered) but increasingly many use React/Next.js. The fallback ensures something is always returned.
- **Source-annotated extraction** (`Fact` dataclass with claim, source_section, source_url, confidence) is excellent design. The agent can never claim something the page didn't actually say — every fact has a traceable source.
- **Tech stack detection** covers 11 major platforms (WordPress, Shopify, Wix, Squarespace, Webflow, Next.js, React, Vue, Drupal, HubSpot). Tested against Stripe (correctly detected Next.js), Vercel (correctly detected Next.js), and MJ Plumbing (correctly detected WordPress 6.9.4 via meta generator).
- **Crawl orchestrator** with three-stage discovery: sitemap.xml → WordPress sitemap fallback → homepage link extraction. Prioritises business-relevant pages (contact, about, services, pricing) over blog posts and other pages.
- **Honest failure handling.** `accessible=False` with human-readable notes when both methods fail. The agent is told explicitly what happened.
- **The `missing` list** conceptually does what the README claims — it tracks things that should have been findable but weren't (no meta description, no contacts, etc.).

### What's broken or weak

**Bug 1: Contact extraction is noisy (false positives).**

Tested against three real websites:

| Site | Real contacts | Extracted | False positives |
|---|---|---|---|
| stripe.com | sales@stripe.com | 4 emails (incl. `damian.michelfelder@example.com`, `jane.diaz@stripe.com`) | 2-3 fake/example emails from testimonial illustrations |
| stripe.com | +1 844... | 3 phone numbers (incl. `2025 99.999`) | `2025 99.999` is clearly a version number, not a phone |
| vercel.com | None found | 0 emails, 1 phone (`1 2 3 4 5 6`) | `1 2 3 4 5 6` is not a phone number |
| mjplumbing.co.uk | 01843 613795, 07885... | 0 emails, 5 phone numbers | `317206626`, `1147218434` are false positives |

The phone regex (`r"\+?\d[\d\s\-().]{7,}\d"`) is too loose. It matches any sequence of 7+ digits separated by spaces, dashes, or parentheses. Version numbers, dates, account numbers, and ID numbers all match. The email regex doesn't filter `@example.com` addresses (which are commonly used in testimonials and illustrations).

**Impact on lead qualification:** A freelancer researching a lead would see fake contact information mixed in with real data. If they used `sales@stripe.com` that's fine, but `damian.michelfelder@example.com` would be embarrassing in a pitch email. The noisy phone numbers are worse — `1 2 3 4 5 6` looks like a real number to someone skimming quickly.

**Bug 2: Missing list is stale after merge.**

The `merge_extractions()` function merges `missing` lists from all crawled pages but doesn't remove items that were subsequently found on later pages.

Example: If the homepage has no contacts (adds "No email or phone number found in body text" to missing), but the contact page does have an email, the merged result contains BOTH the email in contacts AND "No email or phone number found" in missing. This is contradictory.

**Impact on the "specifies what it could not verify" claim:** This is the load-bearing claim of the bundle's positioning. If the missing list says "no contacts found" but the contacts section has an email, the agent (or the freelancer reading the report) gets a confused signal. An agent following the SKILL.md literally would put "No contact information was found on the website" in the Unverified section while also listing an email in the findings. This undermines the credibility of the honesty mechanism.

**Weakness 1: Social link detection is thin.**

| Site | Known social profiles | Detected |
|---|---|---|
| stripe.com | Twitter/X, LinkedIn, YouTube, Instagram, Facebook | 1 (YouTube only) |
| vercel.com | Twitter/X, LinkedIn, GitHub, YouTube | 0 |
| mjplumbing.co.uk | Unknown (likely Facebook for small UK plumber) | 0 |

The extraction only finds social links in `<a>` tags with hrefs matching known social domains. Many sites use:
- SVG icons with links (the href is there but may be inside complex markup)
- Social sharing widgets that load dynamically
- Footer link blocks that Playwright may not fully capture
- Redirect URLs (e.g., `https://t.co/...` instead of `https://twitter.com/...`)

For lead qualification, knowing a business's social presence matters. A freelancer researching a lead would miss most social profiles.

**Weakness 2: Small business page discovery failures.**

Tested against MJ Plumbing (a real UK WordPress plumbing business):

- Playwright loaded the page successfully (status 200)
- Sitemap check: no `/sitemap.xml` found
- WordPress sitemap check: no `/wp-sitemap.xml` found
- Homepage link extraction: **0 pages discovered**
- Only the homepage was analysed

A WordPress site with 0 discovered pages is unexpected. WordPress generates sitemaps by default since version 5.5. The most likely cause: the site uses a custom theme or a page builder (Elementor, Divi) that puts navigation in JavaScript-rendered elements that Playwright captures as rendered HTML but the regex-based link extraction doesn't parse. The `<a href>` regex (`r'<a\s+[^>]*href=["\']([^"\' >]+)["\'][^>]*>'`) should still match standard anchor tags in the rendered HTML, so this might be a more fundamental issue with how Playwright returns the page content.

**Impact:** For a freelancer qualifying a lead, the homepage-only analysis would miss the About page (company history, team size), the Services page (what they actually offer), and the Contact page (phone, email, location). These are the most important pages for lead qualification. The SKILL.md for Lead Qualifier instructs the agent to research "homepage and key pages (About, Services, Contact)" — but if the crawler can't discover those pages, the agent only gets homepage data.

---

## Code Review: templates.py (156 lines)

**Assessment: Minimal, correct, no over-engineering.**

- `{{var}}` substitution and `{{#section}}...{{/section}}` block rendering work correctly.
- Dotted lookup (`client.name`) walks nested dicts.
- Section blocks handle lists (render per item), dicts (render once with merged context), and truthy scalars.
- Reference search paths are comprehensive: env var → installed layout → source-repo layout → module-relative.
- CLI render with `--out` flag writes to disk and prints the path.

Tested with the full proposal template and a realistic context object. All sections rendered correctly, including the nested deliverables list, pricing breakdown, and phases.

No issues found.

---

## The "Specifies What It Could Not Verify" Claim — Deep Analysis

This is the single most important question in the teardown. The bundle's positioning rests on this claim. Here's the full picture:

### What exists architecturally

1. **web_research.py** returns a `missing` list of things that should have been findable but weren't (no meta description, no contacts, etc.). Every fact has a `source_section` and `confidence` level. ✅
2. **Lead Qualifier SKILL.md** mandates an "Unverified / Could Not Confirm ⚠️" section in every qualification report, with explicit rules about what goes there. ✅
3. **Lead Qualifier SKILL.md** scoring rules say "Never inflate the score" and "Acknowledge the uncertainty." ✅
4. **Lead Qualifier SKILL.md** research quality tiers (HIGH/MEDIUM/LOW) are tied to the `data_confidence` field in the database. ✅

### What breaks in practice

1. **The missing list merge bug** (documented above) produces contradictory signals. A freelancer reading a report would see "No contacts found" next to an actual email address. This destroys trust in the honesty mechanism.
2. **The noisy contact extraction** produces false positives. The agent would see `damian.michelfelder@example.com` as a real contact. It wouldn't flag it because the extraction returned it as a HIGH-confidence fact from the page body. The honesty mechanism can't catch extraction errors — it can only flag what the extraction didn't find.
3. **The social link detection weakness** means the agent would report "No social profiles found" for a business that has active Twitter, LinkedIn, and Facebook. The honesty mechanism would correctly flag this as missing — but the freelancer would have to verify it manually, which is extra work the bundle was supposed to save them from.

### The agent layer risk

The entire honesty mechanism depends on the agent (Claude, GPT, whatever) actually following the SKILL.md instructions. If an agent decides to skip the Unverified section, or to inflate a score based on noisy extraction data, the architecture can't stop it. The SKILL.md says "NON-NEGOTIABLE" for the Unverified section, but that's an instruction to an LLM, not a code-enforced constraint.

This is an inherent limitation of the SKILL.md-as-software model, not specific to this bundle. But it means the "specifies what it could not verify" claim is **architecturally supported but not code-enforced**. The extraction layer does its job (returns what it found and what it didn't), but the presentation layer (the SKILL.md instructions to the agent) is advisory.

### Bottom line on this claim

The architecture is genuinely designed for honesty — more so than most competing tools. The `Fact` dataclass with source attribution, the `missing` list, the mandatory Unverified section, the scoring honesty rules — these are all real design decisions that push toward accurate reporting. The merge bug and noisy extraction are fixable implementation issues, not architectural flaws.

**The claim is real, but fragile.** It works when the extraction is clean and the agent follows instructions. It breaks when the extraction produces false positives (which it does, regularly) or when the merge creates contradictory signals (which it does, predictably). For a $19 bundle, this is acceptable. For a product that claims to be the single thing that distinguishes it from competitors, it needs to be more robust.

---

## Skill Composition Analysis

The README says: "Run the full pipeline: qualify a lead, generate a proposal, onboard the project, manage it through the tracker." This implies a composed workflow where each skill's output feeds the next.

### What actually happens

**Data flow:**
```
Lead Qualifier → stores research_notes, lead_score, tags, data_confidence in SQLite
                     ↓ (database row exists)
Proposal Builder → reads database row, but primarily uses user-provided discovery notes
                     ↓ (proposal file + updated database row)
Project Onboarder → reads database row + proposal file
                     ↓ (task rows + project brief file)
Pipeline Tracker → reads all database rows, manages day-to-day operations
```

### The composition gap

The Lead Qualifier produces rich structured data: tech stack, social links, contact information, website quality assessment, research quality tier, and a feasibility score. This data is stored as:

- `research_notes` (free text — a 2-3 sentence summary)
- `lead_score` (integer)
- `data_confidence` (HIGH/MEDIUM/LOW)
- `tags` (comma-separated in the tags table)

The detailed findings (tech stack, social links, contacts, page-by-page analysis) are stored in the **qualification report file** (a markdown document at `~/.webclient-studio/reports/qualifications/...`), not in the database.

The Proposal Builder reads from the database. Its SKILL.md says "Read automatically from database: Research notes (from Lead Qualifier), Lead score and assessment, Tags." But it doesn't read the qualification report file. The detailed findings from lead research (what CMS they use, what social profiles they have, what their website looks like) are not available to the Proposal Builder unless the agent independently reads the report file.

**This is four tools sharing a database, not a composed pipeline.** The skills can be used sequentially, and the data persists between them, but each skill primarily works from user input + database summary, not from the previous skill's structured output.

### Is this a problem?

For the target user (a web freelancer), this is probably fine. The freelancer would naturally carry context between skills — they remember what they learned during lead qualification when they write the proposal. The database stores enough summary data (research notes, score, tags) to jog their memory.

But it means the README's implication of a "full pipeline" is overstated. The skills compose at the data-storage level, not at the output-input level. A truly composed pipeline would have the Proposal Builder reading the full qualification report and using the specific findings (tech stack, contacts, website quality) to inform the proposal's scope and pricing.

**Verdict on composition:** The skills share a database and can be used sequentially. This is useful and functional. But calling it a "composed pipeline" is generous. It's more accurately described as "four related tools with shared data storage."

---

## Implementation Quality Across the Four Skills

| Skill | Custom code | SKILL.md quality | Overall |
|---|---|---|---|
| Lead Qualifier | web_research.py (655 lines) — substantial, well-designed | 297 lines — comprehensive, detailed, clear scoring rules | **Strong** |
| Pipeline Tracker | db_helper.py (967 lines) — substantial, solid | 354 lines — comprehensive, covers all query types | **Strong** |
| Proposal Builder | templates.py (shared, 156 lines) — minimal | 200 lines — good but thinner, relies on agent compliance | **Moderate** |
| Project Onboarder | None (templates.py shared) | 257 lines — good structure, clear edge cases | **Moderate** |

The Lead Qualifier and Pipeline Tracker carry the bundle. They have real code doing real work. The Proposal Builder and Project Onboarder are SKILL.md instructions that rely on the agent to follow them correctly, with template rendering as the only custom code.

This isn't a flaw per se — the SKILL.md instructions are thorough and well-written. But it means the bundle has two strong skills and two moderate skills, not four strong skills. A freelancer would get the most value from the Lead Qualifier and Pipeline Tracker. The Proposal Builder and Project Onboarder are useful starting points but depend heavily on agent quality.

---

## Install Experience

### The README says:
```
./install.sh
```

### Reality:
- **install.sh does not exist.** Neither does install.ps1. The README references a file that was never created.
- The only install guide is `references/setup.md` (184 lines), which is a **10-step manual process** requiring:
  1. Finding the bundle source (checking 4 locations, then asking the user)
  2. Detecting the agent's skills directory (checking 2 locations, then asking the user)
  3. Creating 5 directories manually
  4. Copying shared scripts
  5. Copying references
  6. Copying 4 SKILL.md files to the agent's skills directory
  7. Installing Python dependencies (`pip install requests beautifulsoup4`)
  8. Being prompted about Playwright (mandatory prompt — "You MUST always ask the user")
  9. Running 3 verification checks
  10. Being told setup is complete

### "Zero setup" claim evaluation

| Claim | Verdict | Evidence |
|---|---|---|
| Zero API keys | ✅ True | No API keys required. Confirmed by code review. |
| No external services | ✅ Mostly true | Optional Playwright install is the only external dependency. No cloud services. |
| Zero configuration | ⚠️ Partially true | Database and config are auto-created on first use. But setup requires manual directory creation, file copying, and dependency installation. |
| Zero setup | ❌ False | 10-step manual process with mandatory user interaction. |

The "zero setup" claim is the most visible claim in the README (it's the first bolded line). It's inaccurate. The setup is not terrible — it's about 5 minutes of following instructions — but it's not zero. A freelancer who isn't comfortable with terminal commands would struggle.

### Time-to-value measurement

From `git clone` to `first qualified lead in the pipeline`:

| Step | Time | Notes |
|---|---|---|
| Clone repo | ~5s | Small repo, single commit |
| Read setup.md | ~2 min | 184 lines, needs careful reading |
| Find bundle source | ~30s | If already in the clone directory |
| Find agent skills directory | ~10s | If using OpenClaw or Claude Code |
| Create directories | ~5s | 5 `mkdir -p` commands |
| Copy files | ~5s | 3 `cp` commands |
| Install Python deps | ~30s | `requests` and `beautifulsoup4` |
| Playwright decision + install | ~2-5 min | ~150MB download for Chromium, if accepted |
| Verify installation | ~15s | 3 checks |
| **Total** | **~5-10 min** | Depends on Playwright decision |

First lead qualification would take another 3-5 minutes (running the Lead Qualifier SKILL.md instructions). **Total time-to-value: 8-15 minutes** including Playwright.

Without Playwright (using HTTP fallback only): **~5-8 minutes** total. But the Lead Qualifier would produce lower-quality results on most modern websites.

---

## Pricing Comparison

| Tool | Price | Billing | What it covers |
|---|---|---|---|
| **Bonsai** (Essentials) | $19/month ($228/year) | Monthly/Annual | CRM, proposals, contracts, invoicing, payments, time tracking, client portal, scheduling |
| **HoneyBook** (Starter) | $29/month ($348/year) | Monthly/Annual | CRM, proposals, contracts, invoicing, payments, client portal, templates, AI |
| **Dubsado** (Starter) | $20/month ($200/year) | Monthly/Annual | CRM, proposals, contracts, invoicing, payments, scheduling, forms, workflows, time tracking |
| **DIY (spreadsheets)** | $0 | — | Manual tracking, no automation, no templates, significant time cost |
| **WebClient Studio** | **$19 one-time** | One-time | Lead research, qualification scoring, proposal templates, onboarding checklists, pipeline tracking |

### Fair pricing read

The $19 price point is not competing with Bonsai or HoneyBook on feature parity. Those tools include invoicing, payment processing, contract signing, client portals, and scheduling — things WebClient Studio doesn't do at all. WebClient Studio competes with the **pre-build workflow** specifically: researching leads, scoring them, generating proposals, onboarding clients, and tracking the pipeline.

Against the DIY baseline (spreadsheets + manual research), $19 one-time is very fair. A freelancer spending even 2 hours setting up a spreadsheet pipeline has already spent more than $19 of their time. The lead qualification feature alone (automated website research with tech stack detection and confidence scoring) would save most freelancers 15-30 minutes per lead.

Against SaaS tools, the comparison is: WebClient Studio replaces the pre-build workflow for $19 total, while SaaS tools charge $19-29/month for a broader feature set. A freelancer paying for Bonsai AND using WebClient Studio would have overlapping proposal/pipeline features. But WebClient Studio works locally (no subscription, no data on someone else's server) and integrates directly with the freelancer's AI agent — something no SaaS tool does.

**Fair pricing verdict:** $19 is at the low end of fair, possibly underpriced. A freelancer who lands one additional client through better lead qualification has already gotten 10-50x return on $19.

---

## Specific Research Focus Results

### 1. The "specifies what it could not verify" claim

**Detailed findings above.** Summary: architecturally real, implementation has a merge bug that produces contradictory signals, contact extraction is noisy enough to undermine the honesty mechanism, social link detection misses most profiles. The claim is the bundle's strongest differentiator but also its most fragile.

### 2. The end-to-end workflow under realistic stress

I tested the database operations end-to-end: created 24 leads, moved them through all pipeline stages (lead → qualified → proposal_sent → onboarding → active → lost), added tags, created tasks, tracked activity, searched, exported. The workflow holds up. The database operations are fast, correct, and comprehensive.

I did NOT test the full agent-driven workflow (qualify a lead → generate a proposal → onboard a project) because that requires running the SKILL.md instructions through an actual agent (Claude, GPT, etc.). The code layer works; the agent-compliance layer is untested.

### 3. Implementation quality of Lead Qualifier and Pipeline Tracker

**Lead Qualifier:** The web_research.py module is well-designed but has the extraction noise issues documented above. The SKILL.md instructions are comprehensive (297 lines covering research process, scoring rules, report structure, edge cases). The scoring system is well-thought-out with five weighted factors and explicit honesty rules.

**Pipeline Tracker:** The db_helper.py module is the strongest code in the bundle. The SKILL.md covers every reasonable query variant (354 lines). The stale lead detection is correct. The activity log provides a full audit trail. Export to CSV/JSON works.

---

## What to Watch For (per brief checklist)

| Brief concern | Finding |
|---|---|
| "specifies what it could not verify" fails on realistic inputs | Partially true — merge bug and noisy extraction undermine it. Not a full failure, but fragile. |
| Install script fails on any platform | install.sh doesn't exist. This IS a failure — the README promises it. |
| ClawHavoc-class security issues | None found. Clean bill. |
| SQLite schema causes data loss | Schema is well-designed with proper foreign keys and CASCADE. No data loss risk found. |
| Four skills don't compose | Confirmed. Four tools sharing a database, not a composed pipeline. The README overstates the composition. |
| Implementation quality uneven across skills | Confirmed. Lead Qualifier and Pipeline Tracker are strong. Proposal Builder and Project Onboarder are moderate (SKILL.md-only, no custom code). |

---

## The Fix List (conditions for Stack Play coverage)

### Critical (public-claim failures)

1. **Create install.sh (and ideally install.ps1)** — The README promises `./install.sh`. It needs to exist. The setup.md logic can be scripted into a single command that automates the 10 steps. This should be the top priority fix.

2. **Fix "zero setup" claim** — Either soften the claim ("Minimal setup — 5 minutes") or automate the setup enough that the claim becomes true. The current state (10-step manual install + "zero setup" in bold at the top of the README) is a credibility gap that a critical reader would flag immediately.

### High (implementation bugs that affect the core value proposition)

3. **Fix the missing list merge bug** — In `merge_extractions()`, after merging contacts, remove "No email or phone number found in body text" from the missing list if emails or phones were found. Same for "No meta description tag found" if a meta description was found on any page.

4. **Improve contact extraction accuracy** — Filter out `@example.com` emails. Tighten the phone regex to require a minimum digit count in a single cluster (e.g., at least 6 consecutive digits without spaces) or require a recognisable phone format. Consider a simple validation: if the "phone number" doesn't contain at least 7 consecutive digits, it's probably not a phone number.

5. **Improve social link detection** — The current implementation only finds social links in `<a>` tags with hrefs matching known social domains. Consider also checking for social media metadata (og:image patterns, known embed URLs) and expanding the social host detection to handle redirect URLs.

### Medium (quality improvements)

6. **Improve small business page discovery** — The WordPress sitemap should be found for any WordPress 5.5+ site. Debug why MJ Plumbing's WordPress site returned 0 discovered pages. If the issue is Playwright's HTML output not containing the navigation links (e.g., they're in iframes or shadow DOM), consider adding a Playwright-specific link extraction path that uses `page.query_selector_all('a')` instead of regex on the HTML string.

7. **Add `--json` as an alias for the positional `json` argument in `update-field`** — Prevents the most common usage error. One-line argparse fix.

### Low (nice-to-haves for publication)

8. **Add input validation on lead_score** — Reject values outside 1-10 in the CLI. One-line validation.
9. **Add a CHECK constraint on `data_confidence`** — Restrict to HIGH/MEDIUM/LOW in the SQLite schema.
10. **Add requirements.txt** — `requests`, `beautifulsoup4`, `playwright` (optional).
11. **Remove bundle-review.md from the repo** — This is a working document, not shipping content. It contains internal review notes and correction history.
12. **Add a LICENSE file.**

---

## Candidate Frame for a Hypothetical Stack Play

If this bundle clears the fix list, the Stack Play would write itself around these tensions:

1. **$19 vs $19/month.** The pricing comparison is the obvious hook. Every freelancer tool is a subscription. WebClient Studio is one-time. But the comparison needs to be honest about what's missing (no invoicing, no payments, no contracts).

2. **AI-native vs SaaS-native.** WebClient Studio works through an AI agent, not a web dashboard. This is its real differentiator. The agent does the research, writes the proposals, manages the pipeline — the freelancer just talks to it. No SaaS tool offers this.

3. **Local-first vs cloud-first.** The data stays on the freelancer's machine. No account creation, no data on someone else's server, no vendor lock-in. This matters to freelancers who've been burned by SaaS price hikes or shutdowns.

4. **"Specifies what it could not verify."** If the merge bug is fixed and the extraction noise is reduced, this becomes a genuine selling point. A tool that says "I couldn't find their pricing page" is more useful than a tool that silently scores an 8/10 based on incomplete data.

**Quotable moments for a hypothetical Teardown:**
- The Lead Qualifier returning `damian.michelfelder@example.com` as a real contact (if extraction noise isn't fixed)
- The "zero setup" claim followed by a 10-step manual install (if not fixed)
- The Pipeline Tracker grouping 24 leads by status and sorting by score in 0.030 seconds
- The source-annotated extraction returning `Fact(claim="Stripe is a financial services platform...", source_section="meta[description]", confidence="HIGH")`

---

## Appendix: Test Environment

- **Platform:** Raspberry Pi 5, arm64, Linux 6.12
- **Python:** 3.x (system Python)
- **Dependencies:** requests, beautifulsoup4, playwright + chromium (all installed)
- **Agent platform tested:** OpenClaw (install and database operations verified)
- **Agent platform NOT tested:** Claude Code, Codex CLI, Cursor (no access)
- **Sites tested:**
  - stripe.com — large SaaS, Next.js, clean modern design
  - vercel.com — large SaaS, Next.js, JS-heavy
  - mjplumbing.co.uk — small UK plumbing business, WordPress 6.9.4
- **Database scale tested:** 24 leads, 5 tasks, multiple status transitions
- **Pricing data sourced:** hellobonsai.com/pricing, honeybook.com/pricing, web search for Dubsado (28 April 2026)
