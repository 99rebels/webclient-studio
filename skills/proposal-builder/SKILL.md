---
name: proposal-builder
description: Build a scoped freelance web design proposal from discovery call notes. Use when the user wants to write or generate a proposal, build a proposal from discovery, or create a proposal for a client already in the pipeline. Produces a markdown proposal document and updates the pipeline row.
---

# Proposal Builder

Take discovery call notes plus the lead's existing research, and produce a scoped, professional proposal the client can say yes to. Save it as a markdown file and update the pipeline row's status to `proposal_sent`.

## When to use this skill

Trigger phrases:
- "build a proposal for <client>"
- "write a proposal from our discovery call"
- "create proposal for <client>"
- "generate a proposal"
- "I just finished a call with <client>" → offer to build the proposal
- "they want <services>" → start with scope hints

## Tools

```bash
SHARED="${FREELANCE_FORGE_CONFIG_DIR:-$HOME/.freelance-forge}/shared"
PYTHONPATH="$SHARED" python3 -m db_helper <command>
PYTHONPATH="$SHARED" python3 -m templates render <path> --json '...'
```




## First Run Check

Before the flow below, run the guard clause:
```bash
python3 -c "import sys; sys.path.insert(0, '$HOME/.freelance-forge/shared'); import db_helper" 2>/dev/null && echo OK
```

If `OK` — proceed to Flow.

If it fails — read `~/.freelance-forge/references/setup.md` and execute the setup steps. Once setup completes, return here and proceed with the Flow.


## Flow

### 1. Find the client in the pipeline

```

python3 -m db_helper get-lead --company "<client name>"
```


Three paths:
- **Exactly one match** → continue with that lead row.
- **Multiple matches (fuzzy)** → present them with `id`, `status`, `score`. Ask the user which one.
- **No match** → tell the user. Offer:
  1. Run Lead Qualifier first (recommended — better proposal context).
  2. Create a minimal lead row right now and proceed.
  3. Cancel.

If the user picks (2):
```

python3 -m db_helper add-lead "<client>" --website "<url if known>"
```

Then continue.

### 2. Get discovery notes

If the user already pasted them, use them.

If not, ask: *"Paste the discovery notes — or want me to generate a discovery call template first?"*

If they pick the template, output a structured question list in chat (not a file): goals, audience, features, timeline, budget signal, content readiness, brand preferences, technical requirements. Once they have notes, restart the flow.

**Never invent discovery content.** If notes are too thin, build a minimal proposal with `[Confirm with client: ...]` placeholders.

### 3. Read the full lead row

```

python3 -m db_helper get-lead --id <lead-id>
python3 -m db_helper tag list --lead-id <lead-id>
```


Combine: research notes + tags + lead score (context for tone) + discovery notes (the actual scope).

### 4. First-run pricing strategy check

```

python3 -m db_helper config get
```


If `preferences.pricingStrategy` is `null`, ask the user **once**:

> "Do you have a pricing strategy you'd like me to use going forward? Options: `day_rate`, `project_based`, `value_based`, `tiered`, or skip (use market-informed ranges)."

Persist their choice:
```

python3 -m db_helper config set --path preferences.pricingStrategy --value '"day_rate"'
```


(Use `null` to record "skip / use market ranges".)

### 5. Render and adapt the proposal

```

python3 -m templates render proposal-templates/default.md \
    --json-file /tmp/ctx.json \
    --out "$FREELANCE_FORGE_CONFIG_DIR/reports/proposals/<slug>-<YYYY-MM-DD>.md"
```


The template is a **starting point**, not a form. After rendering, **read the file and adapt it** to the client:
- Reference specific things from discovery notes (shows you were paying attention).
- Use the client's language (if they say "booking system", don't call it "appointment scheduling module").
- Mark gaps as `[Confirm with client: <specific thing>]`. Never fabricate.

### 6. Pricing

Pricing is the most sensitive section. The agent's job is context and structure, not setting the price. Rules (proposal-builder.md §5):

- **Present ranges, not fixed numbers.** "£2,000–£3,500 for a 6-page responsive site with CMS" is right; "£2,750" is wrong.
- Ranges are informed by: service type, scope (pages, features, complexity), the budget signal from research, regional market.
- Always flag: *"Final price is yours to set based on your rate, experience, and the relationship."*
- Never price below market to "win the deal" — that's the freelancer's call, not yours.
- If no pricing signal at all: present a wide range and note: *"Range is wide due to limited scope information. Recommend clarifying scope before finalising."*
- If the user's `pricingStrategy` is set, frame the pricing block in that style (e.g. day rate × estimated days; project-based phases; tiered packages).

### 7. Tone and style

Write in the freelancer's voice — first person ("I recommend...") or first plural ("We suggest..."). Confident but not arrogant. Short scannable paragraphs. **Avoid superlatives** ("revolutionary", "game-changing", "best-in-class"). No jargon the client won't understand.

### 8. Required structure (proposal-builder.md §4)

The template ships with these sections — keep them in this order:

1. **Executive Summary** (2–3 paragraphs) — what they do, why this project matters, what the proposal covers
2. **Scope of Work** — specific deliverables, what's included, what's NOT included, assumptions
3. **Timeline** — phases, milestones, dates as estimates pending content delivery
4. **Investment** (not "Price" or "Cost") — broken down, presented as ranges, payment schedule
5. **Terms & Conditions** — revisions, payment terms, cancellation, IP transfer. Note: "outline, not legal contract"
6. **Next Steps** — what happens if they say yes, how to get in touch, suggested response date

### 9. Update the database

```

python3 -m db_helper update-field <lead-id> \
    '{"proposal_summary": "<2-3 sentence summary, NOT the full proposal>", "proposal_date": "<YYYY-MM-DD>"}'

python3 -m db_helper update-status <lead-id> proposal_sent
```


The shim auto-logs `proposal_created` and `status_changed` (`<old> -> proposal_sent`). If discovery notes were captured separately, also:

```

python3 -m db_helper update-field <lead-id> \
    '{"discovery_notes": "<concise notes, not full transcript>"}'
```


### 10. Optional: covering email draft

Offer once: *"Want a covering email draft for the proposal?"*

If yes, output **in chat only**. Rules (proposal-builder.md §8):
- Reference the discovery call positively.
- 2–3 sentence summary of what the proposal covers.
- Clear call to action.
- Brief — the proposal does the heavy lifting.
- **Never include the price in the email.** Price lives in the proposal.

## Edge cases

| Scenario | Approach |
|---|---|
| Very brief discovery notes ("they want a website") | Minimal proposal with placeholders. Suggest a follow-up call. |
| Discovery contradicts lead research | Trust discovery (more recent, direct from client). Note the discrepancy in scope notes. |
| Lead row exists but has no research | Use discovery notes alone. Less tailored, but functional. |
| Proposal already exists for this client | Alert user. Offer: new version vs update existing file. |
| Discovery mentions out-of-scope features (mobile app, SEO campaign) | Include as "future phase" or "not in current scope" — don't silently drop. |
| Client wants something the freelancer can't deliver | Include with `[Verify capability: ...]` flag — don't filter it out. |
| User says "skip pricing strategy" on first run | Persist `pricingStrategy: null`. Use market-informed ranges. Do not ask again. |

## End-of-turn

Tell the user: file path, status now `proposal_sent`, summary of what was included, any `[Confirm with client: ...]` placeholders left in the document. Offer the optional covering email.

Example:
> Wrote `~/.freelance-forge/reports/proposals/acme-plumbing-2026-04-26.md`. Status updated to `proposal_sent`. The proposal has 2 placeholders to confirm with the client (booking system features, content delivery deadline). Want a covering email draft?
