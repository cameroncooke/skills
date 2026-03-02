# Agent Skills

A curated collection of custom skills for AI coding agents — designed to automate repetitive developer workflows around releases, changelogs, code review, and knowledge sharing.

## Skills

### changelog-updater

Keeps your CHANGELOG up to date by analysing git history and writing user-facing release notes.

Compares commits between the latest tag and `main`, clusters them by outcome, and writes concise **Added / Changed / Fixed / Breaking** sections. Handles prerelease tags (e.g. `v2.0.0-beta.1` merges into the canonical `2.0.0` section), attributes external contributors, and links new CLI commands or config options to their docs. Breaking changes include migration guides with before/after code examples.

**Invoke with:** `/changelog-updater`

---

### pr-learning

Mines PR review feedback to surface repeatable rules and learnings for your team.

Collects review comments across one or more PRs using `gh`, normalises them into observations, and clusters repeated patterns. Proposes ranked **Rule** (strict) and **Learning** (soft) candidates with confidence scores, dedupes against items already in your AGENTS.md / CLAUDE.md, and — after your approval — codifies them with full provenance tracking (source PRs, semantic keys, confidence).

**Invoke with:** `/pr-learning`

---

### release-tweet

Drafts a release announcement tweet from a GitHub release — ready for you to review and post.

Fetches release notes via `gh`, parses Added/Changed/Fixed/Removed sections, and condenses them into outcome-focused bullet points. Identifies external contributors, cross-references their X/Twitter handles with multi-signal verification, and outputs the composed tweet text alongside a confidence table for each handle lookup.

**Invoke with:** `/release-tweet`

---

### agent-change-walkthrough

Generates a narrative walkthrough of AI-authored code changes, ordered by dependency then runtime flow.

Weaves changed and unchanged code into a single story — from the trigger that kicks things off to the final observable behaviour. Each step includes annotated mini-diffs with `path/to/file:line` headers, concrete input/output examples for data-shape changes, and inline notes on trade-offs, alternatives, and risks.

**Invoke with:** `/agent-change-walkthrough`

---

### reconcile-merge-conflicts

Resolves merge and rebase conflicts with branch-aware reconciliation and regression-focused decision making.

Detects whether a merge or rebase is active, asks for the target when none is in progress, then resolves conflicts file-by-file by preserving important intent from both sides while treating the target branch (usually `main`) as canonical for current behavior. Produces a confidence-ranked reconciliation audit with risks, evidence, and open questions.

**Invoke with:** `/reconcile-merge-conflicts`

---

### pr-comment-resolution

Audits and resolves PR review comments with an evidence-first workflow.

Collects PR feedback through the skill’s helper scripts, then classifies each item as valid/invalid/contentious/already-addressed/out-of-scope using direct code evidence. Default collection is focused on unresolved review threads and standalone comments, with optional views for counts/bodies/thread locations to reduce token usage. After approval, it can help apply scoped fixes, post replies, and resolve threads with commit-linked rationale.

**Invoke with:** `/pr-comment-resolution`

---

## Installation

Install individual skills directly from this repo with `npx skills add`:

```bash
npx skills add cameroncooke/cameroncooke-skills@agent-change-walkthrough
npx skills add cameroncooke/cameroncooke-skills@changelog-updater
npx skills add cameroncooke/cameroncooke-skills@pr-learning
npx skills add cameroncooke/cameroncooke-skills@release-tweet
npx skills add cameroncooke/cameroncooke-skills@reconcile-merge-conflicts
npx skills add cameroncooke/cameroncooke-skills@pr-comment-resolution
```

You can also install manually by copying skill directories into your agent's skills folder:

| Agent | Skills path |
|---|---|
| **Claude Code** | `~/.claude/skills/` |
| **Others** | `~/.agents/skills/` |

Each skill is self-contained — copy only the ones you need.
