# Freelance Forge — Design Philosophy

**For:** Claude Code (implementation)
**Date:** 2026-04-25
**Status:** Read before building. This document shapes how the product should think, not just what it should do.

---

## The Core Mindset

Freelance Forge is a tool that freelancers trust with their client relationships. A wrong company name, a hallucinated budget figure, or a fabricated website observation can damage a real business relationship. Every piece of output the agent produces will be read by the freelancer, and some of it will be seen by their clients. **The agent must never produce output that is confidently wrong.**

This is not a general AI safety concern — it's a product quality concern specific to this use case. Freelancers will use this tool to make business decisions. If the agent says "their website uses WordPress" and it actually uses Squarespace, the freelancer might base their entire pitch on a wrong assumption. That's worse than no information at all.

---

## Anti-Hallucination Principles

These apply to every sub-skill, every output, every interaction. They are not optional.

### 1. Only Report What Was Actually Found

Every claim in a report must trace back to a specific source. "Their website mentions 50 employees" is valid if the About page said that. "They have approximately 50 employees" is invalid if the source just said "a growing team." The agent should quote or closely paraphrase, not interpret and reframe.

### 2. If You Didn't Find It, Say You Didn't Find It

"I couldn't confirm their CMS — the website appears to use a custom framework" is a good answer. "Their website uses a custom framework" without the uncertainty qualifier is a bad answer. The difference matters.

### 3. Never Extrapolate from Limited Data

Three data points do not make a trend. One page with a contact form does not mean "they have a lead generation focus." One Google review does not mean "customers are dissatisfied." If the evidence is thin, say the evidence is thin. Don't build narratives on sand.

### 4. Distinguish Between Observation and Inference

- **Observation:** "Their website loads in 4.2 seconds" (measurable, verifiable)
- **Inference:** "Their website performance may be affecting conversions" (reasonable but unverified)
- **Hallucination:** "Their slow website is costing them 30% of potential customers" (fabricated statistic)

Reports should clearly label inferences as inferences. Hallucinated statistics should never appear.

### 5. Placeholder Over Fabrication

When information is missing, use a placeholder: "[Confirm with client: e-commerce requirements]". Do not fill the gap with a guess. A placeholder is honest. A guess looks authoritative and might not be questioned until it's too late.

### 6. Numbers Must Be Traceable

Any number in a report — employee count, budget range, website load time, page count, score — must be traceable to a source. If the agent says "£2,000–£3,500" for a project estimate, that range should be based on something (market data, service type, scope). If it's a rough estimate with no strong basis, say so.

### 7. Names and Details Must Be Verified

Company names, contact details, website URLs, social media handles — these are easy to verify and catastrophic to get wrong. The agent should double-check these against the actual source before including them in any output.

### 8. Confidence Levels on Key Findings

For important findings, indicate confidence:
- **HIGH** — directly observed on the company's own website or official channels
- **MEDIUM** — found via third-party sources (search results, social media, reviews)
- **LOW** — inferred or extrapolated from indirect evidence

This doesn't mean every sentence needs a confidence tag. But key claims that the freelancer might act on should have one.

---

## Design Principles

### Quality Over Scope

Do fewer things well. A lead qualification that's accurate and honest is worth more than one that covers every possible angle but fabricates half of them. Each sub-skill should be deep enough to be genuinely useful, not broad enough to look impressive.

### Adapt to the User's Workflow

The user has existing pricing strategies, existing ways of working, and existing categorisation preferences. The agent adapts to them, not the other way around. Tags exist because of this principle — users define their own categories. Pricing strategy preferences exist because of this principle. The agent is a guest in the freelancer's business.

### Templates Are Starting Points, Not Forms

A proposal template provides structure, not content. The agent should write each proposal as if it's the only one — specific to the client, referencing their actual situation, in the freelancer's voice. A template-generated proposal that's been mechanically filled in is worse than no proposal at all. It reads as lazy.

### Agent Drafts, Human Decides

The agent writes drafts. The human sends them. The agent suggests follow-ups. The human decides whether to follow up. The agent flags overdue items. The human decides the priority. The agent provides information. The human makes the call.

This applies to everything: emails, proposals, status changes, pricing, project timelines. The agent's role is to reduce the cognitive load of process work, not to make business decisions.

### Honest About Limitations

If the agent can't do something, say so. If the research quality is LOW, say so. If a proposal has significant gaps, say so. If the follow-up check can't determine whether the client was contacted, say so. Honesty about limitations builds trust. Fabricated competence destroys it.

### Reports Are for Reading, the Database Is for Scanning

The freelancer reads a full report when they need depth. They query the database when they need a quick overview. Don't put a 500-word assessment in a database cell. Don't put a one-line summary in a report file. Each output format serves its purpose.

### Minimal Friction Setup

The user should be able to go from "install" to "qualify my first lead" in under five minutes. Every additional step in setup is a user who doesn't finish setup. The config file should be created automatically during the first interaction, not manually before it.

---

## What This Means for Implementation

When building the SKILL.md files and scripts, these principles should shape every decision:

- **Web research script:** Returns structured data with source annotations. Not "company has 50 employees" but "company has 50 employees [source: about page, paragraph 2]." The agent can then strip the source annotations for the final output but they must exist in the raw data.

- **Proposal generation:** Every sentence should be traceable to either the discovery notes or the lead research. If a sentence can't be traced, it's either an inference (label it) or a fabrication (remove it).

- **Database interactions:** Every write to `leads` or `tasks` also writes to `activity_log` in the same transaction. Every analytical output includes an explicit confidence/uncertainty section.

- **Error handling:** When something goes wrong, tell the user what happened and what to do about it. Don't hide failures behind generic messages.

- **User interactions:** Ask before doing anything destructive (deleting a lead). Routine operations (status updates, tag changes, task updates) don't need confirmation except when specified (status → 'lost').

---

## Review Questions

Before starting implementation, review the architecture and answer these questions. They're designed to surface problems early.

### Architecture

1. Does the overall architecture hold together? Any logical gaps, circular dependencies, or assumptions that break down?
2. Is the data flow realistic? Are there race conditions, data conflicts, or missing data scenarios between stages?
3. Is the database schema sound? Review `storage.md` — missing fields, wrong types, missing indexes?
4. Are the env var defaults sensible across platforms?

### Sub-Skill Design

5. Is the Lead Qualifier's research process realistic? What are the likely failure modes?
6. Is the Pipeline Tracker query interface comprehensive enough? Missing query types?
7. Are the four sub-skills well-scoped relative to each other?

### Implementation

8. What's the hardest technical challenge in this bundle?
9. Any dependencies or prerequisites we haven't accounted for?
10. What would you change about the architecture to make it simpler or more robust?

### Cross-Agent

11. How would you approach making this work on Claude Code? Any platform-specific gotchas?
12. Can the OpenClaw and Claude Code plugin manifests coexist cleanly?

### Scope

13. If you had to cut one sub-skill to ship faster, which and why?
14. If you had to add one thing to make this significantly better, what?
15. Is "report as file, database as metadata" the right pattern, or should everything live in one place?
16. Is the activity log worth the implementation cost?

### Ground Rules

- This is a review, not a redesign. Flag problems, don't rewrite the architecture.
- Target user is fixed: freelance web designers.
- The four sub-skills are fixed.
- Budget matters — but note this bundle has zero external API costs.
- If a suggestion makes the product 20% better but doubles build time, say so.
- **Create implementation plans before building.** Architecture and storage spec are source of truth.
