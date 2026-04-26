# Sub-Skill Deep Dive: Proposal Builder

**Parent:** Freelance Forge — `architecture.md`
**Version:** 0.2 — Design Phase (updated for local SQLite storage)
**Date:** 2026-04-26

---

## 1. Purpose

The Proposal Builder takes discovery notes from a client call and generates a scoped, professional proposal. It combines the lead research (from Lead Qualifier) with what the freelancer learned during discovery to produce a document the client can say yes to.

**It does three things:**
1. **Synthesise** — merge pipeline data (research notes, score, context) with fresh discovery notes
2. **Generate** — produce a structured proposal document with scope, timeline, and pricing guidance
3. **Store** — save the proposal as a file, update the database with a summary

---

## 2. When It Triggers

**Primary triggers:**
- "build a proposal for [client]"
- "write a proposal from our discovery call"
- "create proposal for [client]"
- "generate a proposal"

**Context triggers:**
- "I just finished a call with [client]" → offer to build a proposal from the notes
- "they want [services]" → start proposal with scope hints

---

## 3. Input

The Proposal Builder needs two things:

**Required:**
- **Client identification** — a company name that matches a row in the pipeline database
- **Discovery notes** — the user's raw notes from a discovery call or client interaction. These can be pasted directly, dictated, or referenced from a file.

**Read automatically from database:**
- Research notes (from Lead Qualifier)
- Lead score and assessment
- Tags (service type, budget signals, etc.)
- Any other context stored in the lead's row

### When Discovery Notes Are Missing

If the user triggers the Proposal Builder without providing discovery notes:
- Don't guess or fabricate content
- Offer two options:
  1. "Paste your discovery notes and I'll build the proposal"
  2. "I can generate a discovery call template to guide your conversation first"
- The template should be a structured list of questions covering: goals, audience, features, timeline, budget, content, brand preferences, technical requirements

---

## 4. Proposal Structure

The proposal should follow a consistent structure but adapt its content to the specific client. It's not a fill-in-the-blanks template — it should read as if the freelancer wrote it based on their understanding of the client's needs.

### Sections

**Executive Summary** (2-3 paragraphs)
- What the client does and what problem they're solving
- Why this project matters to their business
- What the proposal covers at a high level

**Scope of Work** (the core section)
- Specific deliverables (e.g., "Responsive website with 8 pages", "CMS integration", "contact form with email routing")
- What's included (e.g., "up to 3 rounds of revisions", "mobile optimisation", "basic SEO setup")
- What's explicitly NOT included (e.g., "ongoing maintenance", "content writing", "photography")
- Any assumptions made (e.g., "assumes client provides all copy and images")

**Timeline** (realistic, not aspirational)
- Phases with approximate durations
- Key milestones and deliverable dates
- Note that dates are estimates pending client approval and content delivery
- Flag any dependencies on the client (e.g., "content delivery by Week 2 required to meet this timeline")

**Investment** (not "Price" or "Cost")
- Broken down by phase or deliverable
- Presented as ranges if exact pricing is uncertain — the freelancer sets the final number
- Include what the pricing covers (and doesn't)
- Payment schedule (e.g., "50% upfront, 50% on completion" or phased payments)
- The agent should suggest ranges based on service type, scope, and market, but clearly indicate these are starting points

**Terms & Conditions** (lightweight, not legal)
- Revision policy (number of included revisions, cost of additional revisions)
- Payment terms and methods
- Project cancellation policy
- IP / ownership transfer
- Note: "This is a project outline, not a legal contract. A formal contract will be provided before work begins."

**Next Steps** (clear call to action)
- What happens if they say yes (sign-off process, kickoff call, onboarding)
- How to get in touch with questions
- A suggested response date

### Gaps in Information

If the discovery notes don't cover something the proposal needs, don't fabricate content. Instead, insert a clear placeholder:

```
[Confirm with client: specific features needed for the booking system]
[Confirm with client: whether email marketing integration is required]
```

These placeholders serve a dual purpose: they keep the proposal honest, and they give the freelancer a checklist of things to verify before sending.

---

## 5. Pricing Philosophy

Pricing is the most sensitive part of the proposal. The agent's role is to provide context and structure, not set the price.

**Principles:**
- Present ranges, not fixed numbers (e.g., "£2,000–£3,500 for a 6-page responsive site with CMS" rather than "£2,750")
- Ranges should be informed by: service type, scope (pages, features, complexity), the client's apparent budget signal from the lead research, and market rates for the region
- Always flag that the freelancer should set the final price based on their own rate, experience, and relationship with the client
- Never price below market rate to "win the deal" — that's the freelancer's decision, not the agent's
- If no pricing signal exists at all, present a broad range with a note: "Pricing range is wide due to limited scope information. Recommend clarifying scope before finalising."

### Pricing Strategy Preferences

Freelancers often have established pricing approaches. On first use of the Proposal Builder, check the config for a `pricingStrategy` preference. If it doesn't exist, ask the user:

- "Do you have a pricing strategy you'd like me to use? For example: day rate, project-based, value-based, or tiered packages?"
- If they have one: default to their strategy and apply it to proposals going forward. Save the preference in config.
- If they don't: use market-informed ranges as described above.

This is a one-time setup — the preference persists in config. The freelancer can always override pricing in any individual proposal.

---

## 6. Tone & Style

The proposal represents the freelancer. It should read like a professional consultant wrote it, not a template engine.

**Do:**
- Write in the first person or first person plural ("I recommend..." or "We suggest...") — the freelancer's voice
- Reference specific things from the discovery notes (shows they were paying attention)
- Be confident but not arrogant
- Use the client's language (if they say "booking system", don't call it "appointment scheduling module")
- Keep paragraphs short and scannable

**Don't:**
- Use jargon the client won't understand
- Be overly formal or stiff
- Include unnecessary technical details (the client doesn't care about CSS frameworks)
- Over-promise on timeline or scope
- Use superlatives ("revolutionary", "game-changing", "best-in-class")

---

## 7. Database Interaction

### Prerequisite Check
The database helper handles this automatically — if the database doesn't exist, it's created. No manual setup required.

### Reading the Lead Row
- Search the leads table by company name
- Read: research notes, lead score, tags
- Combine with the discovery notes the user provides

### If the Client Isn't in the Pipeline
The Lead Qualifier should have been run first. Options:
1. Suggest running the Lead Qualifier first (recommended — gives better context for the proposal)
2. Create a minimal lead row with just the company name and "qualified" status, then proceed
3. Build the proposal from discovery notes alone (weaker, but possible)

Let the user choose.

### Updating the Pipeline
After the proposal is generated:
- Write a brief summary to the proposal_summary field (2-3 sentences, not the full proposal)
- Set the proposal_date to today
- Update status to "proposal_sent"
- Log: `discovery_added`, `proposal_created`, `proposal_sent` in activity_log

---

## 8. Output

**Primary output:** A markdown file saved to `$FREELANCE_FORGE_CONFIG_DIR/reports/proposals/[client-name]-proposal-[date].md`

**Secondary output:** Database row updated with summary and status change

**Activity log:** `discovery_added`, `proposal_created`, `proposal_sent`

**Optional:** Draft an email in chat that the freelancer can use to send the proposal. The email should:
- Reference the discovery call positively
- Summarise what the proposal covers in 2-3 sentences
- Include a clear call to action
- Be brief — the proposal itself does the heavy lifting
- Never include the price in the email — that's what the proposal is for

---

## 9. Edge Cases

| Scenario | Approach |
|---|---|
| Very brief discovery notes ("they want a website") | Build a minimal proposal with more placeholders. Suggest scheduling a follow-up call to fill gaps. |
| Discovery notes contradict lead research | Trust the discovery notes (more recent, direct from client). Note the discrepancy in a comment. |
| Client is in pipeline but has no lead research | Proceed using only the discovery notes. The proposal may be less tailored but still functional. |
| Proposal already exists for this client | Alert the user. Offer to create a new version or update the existing one. |
| Discovery notes mention features outside web design scope (e.g., mobile app, SEO campaign) | Include them in the proposal as "future phase" or "not in current scope" rather than ignoring them. |
| Client wants something the freelancer can't deliver | Don't filter it out. Include it in the scope section with a note: "[Verify capability: e-commerce integration with custom inventory system]" |

---

## 10. Design Decisions

### Why Proposals Are Files, Not Database Rows
Proposals are 1,000-2,000 word documents that the freelancer will send to clients. They need to be formatted, shareable, and possibly exported to PDF. A database cell is not the right place for this — a markdown file gives the freelancer more flexibility (convert to PDF, paste into Google Docs, email directly).

### Why Pricing Is Ranges
The freelancer knows their own value, overhead, and relationship with the client. Setting a fixed price would either undersell the freelancer or scare off the client. Ranges provide a starting point for the freelancer to adjust.

### Why "Investment" Not "Price"
It's a small framing choice but it matters. "Investment" frames the cost as value returned. "Price" frames it as money spent. Freelancers who use this language tend to close more deals. The agent should mirror professional sales language, not retail language.

### Why We Don't Fill Gaps with Assumptions
A proposal with "[Confirm with client: whether they need e-commerce]" is better than a proposal that assumes e-commerce and gets it wrong. Placeholders are honest. Assumptions are risky when presented as fact in a client-facing document.

---

## 11. Claude Code Implementation Notes

### What's Fixed
- The proposal structure (§4): Executive Summary → Scope → Timeline → Investment → Terms → Next Steps
- Pricing as ranges, not fixed numbers (§5)
- Tone principles (§6)
- Placeholder approach for missing information
- Database reads the lead row, writes summary + status
- Email draft is optional, chat output only
- Activity logging: `discovery_added`, `proposal_created`, `proposal_sent`

### What Claude Code Has Freedom On
- Exact SKILL.md wording and structure
- The reference templates (how detailed, what format)
- How to combine research notes + discovery notes into coherent prose
- The specific pricing range methodology
- How to present the proposal in the chat (full text vs. summary + file path)
- Discovery call template content and structure
- Error handling specifics
