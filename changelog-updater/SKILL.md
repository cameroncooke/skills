---
name: changelog-updater
description: Update upcoming CHANGELOG release notes with user-facing outcomes. Use when asked to update changelog entries, prepare release notes, reconcile changelog content with git history, or audit release-note drafts.
---

# Changelog Updater

## Your role

You are a Product Manager writing release notes. Not a developer summarising git log.

Your readers are people and AI agents who **use** this product. They care about three things:

1. What can I do now that I couldn't before?
2. What works better than it did?
3. What broke or changed that I need to act on?

They do not care about implementation details, internal refactors, or how things work under the hood.

## Before writing anything

1. Read `README.md` and any user-facing docs (install guides, CLI usage, quickstart).
2. Understand what the product does and who uses it.
3. Every bullet you write must make sense to someone who has only read those docs.

## Find the changelog and pick the target section

Find the changelog file (`CHANGELOG.md`, `Changelog.md`, or project equivalent). Preserve existing heading style and ordering.

### Decision tree (first match wins)

| Condition | Action |
|---|---|
| `Unreleased` exists **and** unreleased `## [X.Y.Z]` exists (no stable `vX.Y.Z` tag) | Merge `Unreleased` into `## [X.Y.Z]`, remove `Unreleased`. |
| Latest tag is prerelease (e.g. `v2.0.0-beta.1`) and changelog has `## [2.0.0]` | Update `## [2.0.0]`. Do not create `Unreleased`. |
| Top section is `## [X.Y.Z]` with no stable `vX.Y.Z` tag | Treat as upcoming, update it. Do not create `Unreleased`. |
| Only `Unreleased` exists, no unreleased version section | Update `Unreleased`. |
| No active draft section | Create `## [Unreleased]`, then update it. |

Prerelease normalisation:
- Drop prerelease suffixes to get the canonical version: `v2.0.0-beta.1` and `v2.0.0-rc.2` both map to `2.0.0`.
- Keep one canonical section (`## [2.0.0]`), not separate beta sections.
- Canonical prerelease-backed section takes precedence over `Unreleased`.

**Invariant:** exactly one active upcoming section must exist after your update.

### Commit range

```bash
main_ref="origin/main"
git rev-parse --verify origin/main >/dev/null 2>&1 || main_ref="main"

latest_tag="$(git tag --merged "$main_ref" --sort=-creatordate | head -n1)"
if [ -n "$latest_tag" ]; then
  delta_range="${latest_tag}..${main_ref}"
else
  first_commit="$(git rev-list --max-parents=0 "$main_ref" | tail -n1)"
  delta_range="${first_commit}..${main_ref}"
fi

git log --reverse --pretty=format:'%H%x09%s' "$delta_range"
```

If the active section is tied to prereleases, keep existing bullets and merge in new deltas. Do not wipe the section.

## Decide what to include

For every commit or group of commits, ask:

> "Would a user or agent notice this change during normal usage?"

- **Yes** — write a bullet describing the outcome.
- **No** — skip it entirely. No bullet needed.

Changes that are almost always skipped:
- Internal refactors, code restructuring, renaming internals
- Test additions or routine CI pipeline changes
- Dependency bumps with no user-visible effect
- Documentation changes (unless they fix a significant user-facing gap)

### Never skip these

Some changes look internal but directly affect users. Always include:

- **Security fixes** — even in CI, release pipelines, or build infrastructure. A vulnerability in the release workflow is a supply chain security issue that affects every user who installs the package. Frame the bullet around the risk that was closed.
- **Agent-facing improvements** — tool descriptions, next-step suggestions, and guided workflows are the product's UX for AI agents. If tool guidance was wrong, missing, or caused agents to take redundant/incorrect actions, that is a user-visible fix or improvement. Frame the bullet around the agent behaviour change the user would notice (e.g., "agents no longer double-build when running an app").
- **Documentation shipped with the product** — if the project distributes skill files, config schemas, or other docs that agents or tools read at runtime, fixes to those are user-facing fixes, not just "docs changes."

**Do NOT map commits 1:1 to bullets.** Many commits produce zero bullets. Several related commits often produce one bullet. Cluster by outcome, not by commit.

A major release with many commits should typically produce a handful of focused bullets plus expanded sections for significant features — not an exhaustive list. Aim for quality and clarity over completeness. If a bullet doesn't meaningfully help the reader, cut it.

### New-in-this-release rule

If a feature is **new in this release**, bugs fixed and improvements made during its development are not separate bullets. The user has never seen the feature before — they don't need the journey, just the destination. This applies to "Changed" and "Fixed" alike.

- BAD: `Added new CLI mode.` + `Fixed CLI direct-invocation calling the wrong command.` (the user never saw the broken version)
- BAD: `Added new CLI mode.` + `Improved CLI reliability when running commands.` + `Reduced background resource usage by auto-exiting after 10 minutes.` (these are just how the CLI works — not separate improvements to something the user already had)
- GOOD: `Added a first-class CLI interface for direct terminal usage, scripting, and CI workflows.` (fixes and polish are absorbed into the feature)

Only list a fix or improvement separately if it applies to something the user already had in a previous release.

## Working with existing content

The changelog may already contain detailed bullets, narratives, code examples, or migration guides. Audit everything against this skill's rules — but recognise that detail and expansion are often intentional.

- If existing content is already well-written and outcome-focused, **keep it**. You may improve readability, grammar, and clarity — but preserve the original intent, ambition, and the point the author was making. Do not flatten, condense, or heavily rewrite content that already works.
- If existing content is overly technical or violates the rules of this skill, rewrite it into outcome language or remove it.
- If a section uses richer formatting (subheadings, code blocks, narrative paragraphs, doc links), assume the detail level is intentional. Keep that structure unless it is purely internal/technical.
- Preserve existing dates on version headings (e.g. `## [2.0.0] - 2026-02-02`).
- Preserve custom section names (e.g. `### New!`) — they signal intent about how prominent a feature should be.
- When merging `Unreleased` into a version section, integrate the unreleased items into the existing content — do not replace the existing content with a rewrite.
- If the user explicitly asks for an audit, do full reconciliation and remove all stale bullets — but still preserve code examples and migration guides in Breaking.

## Write the notes

Describe the **outcome**, never the **implementation**.

### Before and after examples

| BAD (technical / implementation-focused) | GOOD (outcome-focused) |
|---|---|
| Improved CLI reliability by running non-persistent commands directly and auto-starting background state handling only for commands that need persistent state. | Improved CLI reliability when running commands. |
| Improved Xcode IDE workflow reliability with automatic IDE state sync and stricter tool availability checks. | Improved reliability of Xcode IDE workflows. |
| Made tool names and descriptions more concise to reduce token usage. | Reduced token usage so your agent has more context available for actual work. |
| Refactored daemon routing to use stateless dispatch. | *(skip — user doesn't see this)* |
| Added idle shutdown manager for background processes. | Reduced background resource usage during long idle sessions. |
| Hid internal bridge tools behind a debug flag. | Simplified the tool list by hiding troubleshooting-only tools unless debug mode is enabled. |

### Banned terms in release bullets

These terms must **never** appear in Added, Changed, or Fixed bullets: daemon, routing, bridge, parser, fallback, state machine, stateless, stateful, manifest, dispatch, resolver, handler, middleware, affinity, socket (unless user-facing), internal flag names, manifest field names.

If you cannot write the bullet without one of these terms, either:
- Rewrite it as a pure outcome, or
- Skip it (the change is probably internal).

The **only** exception is the Breaking section, where technical migration details are necessary. Even there, pair every technical term with the user impact.

### Categorise by user impact

Use `Added`, `Changed`, `Fixed`, and `Breaking` headings (match existing project format).

| What happened | Section |
|---|---|
| New capability the user can rely on | `Added` |
| Something works better (reliability, performance, UX, compatibility, defaults) | `Changed` |
| Bug fix or regression fix | `Fixed` |
| Behaviour change that requires user action or breaks existing usage | `Breaking` |

## Documentation links

When a changelog bullet describes a change to the tools, CLI, API surface, or configuration, link to the relevant documentation so users know where to learn more.

### Discovering doc references from commits

During commit analysis, check whether the commits that introduced a feature or change also touched files in `docs/`, `skills/`, or other user-facing documentation directories:

```bash
# For each feature-related commit or PR range, find co-changed docs
git diff --name-only <commit>^ <commit> -- 'docs/' 'skills/' '*.md'
```

If a feature commit and a doc change share the same commit, PR, or are adjacent in the log, the doc is the canonical reference for that feature. Check the headings in those files to find the most specific anchor.

### What to link

Add a doc link when a bullet describes:
- A new tool, command, or CLI subcommand
- A new or changed configuration option, parameter, or workflow
- A new integration or setup path

Do **not** add doc links to:
- Bug fixes (unless the fix changes how users interact with a feature)
- Behavioural guidance changes (e.g. "agents now prefer X tool")
- Internal or security-only improvements

### Link format

Append the link at the end of the bullet, after any PR reference and contributor attribution:

```
- Added session defaults profiles for switching between configurations. See [docs/SESSION_DEFAULTS.md](docs/SESSION_DEFAULTS.md#namespaced-profiles).
- Added `init` command ([#236](link) by [@user](link)). See [docs/SKILLS.md](docs/SKILLS.md#install).
```

Use an anchor (`#heading-slug`) when the doc has a specific section for the feature. Use just the file path when linking to the doc as a whole. Match the project's existing link convention (relative paths or full GitHub URLs — whichever is already used in the changelog).

### Excluded directories

Never link to `docs/dev/` or similar internal developer documentation directories. These are contributor-facing, not consumer-facing. Only link to docs that a user or agent would read.

### When no doc exists

If a feature-level change has no corresponding documentation, do not fabricate a link. Write the bullet without one. Optionally flag it in the output summary as a bullet that could benefit from a doc link.

## Breaking changes

Breaking changes are where detail matters most. Users need enough information to act.

Every breaking item must include:
1. What changed.
2. Who is affected.
3. What breaks if they do nothing.
4. What they need to do to migrate — including **before/after code examples** when config formats, CLI invocations, or API contracts change.

Use subheadings, narrative paragraphs, and code blocks freely in this section. Terse bullets are not enough for breaking changes — show people exactly what to change.

Never bury breaking changes inside regular bullets.

## Significant new features

Not every addition is a bullet point. When a release introduces a significant new capability, consider its scope and impact on the audience and expand accordingly.

For high-impact features, go beyond a single bullet:
- Use a subheading to give the feature its own space.
- Write a short narrative paragraph explaining what it enables and why it matters.
- If the feature requires user setup or education (e.g. a new config file, a new CLI mode, a new workflow), show them how to get started — include a quick example, a code snippet, or a link to the relevant docs.
- Link to detailed documentation so users can go deeper.

A single bullet like "Added project-level configuration via config file" tells users nothing actionable. Instead, explain what the config enables, show a minimal example or link to the config docs, and explain what this replaces or improves.

The goal: a user reading the changelog should be able to understand the feature and start using it, or at minimum know exactly where to look next.

## Contributor attribution

Acknowledge external contributors who materially wrote the code for a change.

### How to identify contributors

For each commit in the delta range, check the commit author (`git log --format='%an'`) and the PR author (`gh pr view <number> --json author`). A contributor is **external** if they are not the repository owner or a core maintainer.

When a PR has commits from multiple authors, check who wrote the substantive code vs. who opened/merged the PR. Attribute based on who authored the implementation, not who merged it.

### Attribution format

Append attribution to the end of the relevant bullet, using the project's existing link style:

```
- Fixed the thing ([#123](https://github.com/org/repo/pull/123) by [@username](https://github.com/username)).
```

### Rules

- **Never attribute the repository owner or core maintainers.** Their work is the baseline — the changelog is written from their perspective.
- **Only attribute for code contributions.** If someone reported an issue but the owner implemented the fix, reference the issue but do not use `by @reporter`. Use `([#123](https://github.com/org/repo/pull/123))` without `by`.
- **Do attribute when an external contributor authored the implementation**, even if the owner opened the PR, added follow-up commits, or merged it.
- If multiple external contributors co-authored a change, list them: `by [@a](https://github.com/a) and [@b](https://github.com/b)`.
- Bot accounts (dependabot, renovate, fix-it-felix, etc.) are never attributed.

### Discovering the repository owner

Check `git log --reverse --format='%an' | head -1` or the repository's GitHub owner. When in doubt, check who has the most commits — they are likely the owner. Do not attribute them.

## Catch-all for filtered work

When the commit range contains a meaningful volume of skipped internal work (refactors, test improvements, CI hardening, dependency updates, internal reliability work), add a single closing line after the last categorised section and before `### Removed` (if present) or at the end:

```
Various other internal improvements to stability, performance, and code quality.
```

This acknowledges the effort without cluttering the notes. Only add this line when there are genuinely many filtered commits (roughly 10+). Do not add it for small releases where every commit maps to a bullet.

## Final checks

Before outputting, verify:

1. Correct section selected per the decision tree.
2. Exactly one active upcoming section exists.
3. Prerelease tags normalised to one canonical section.
4. Every bullet describes a user-visible outcome.
5. No banned terms appear outside the Breaking section.
6. A user who has only read the README would understand every bullet.
7. Empty sections removed (unless project convention keeps them).
8. Security fixes, agent-facing improvements, and product-shipped docs fixes were not skipped.
9. External contributors are attributed; the repo owner is never attributed.
10. Catch-all line is present when 10+ commits were filtered out, absent otherwise.
11. Bullets for new or changed tools/CLI/config link to relevant docs discovered from co-changed files.

## Output

Return:
1. Which section was selected and why (decision tree branch).
2. Whether sections were merged and what was removed.
3. Commit range used.
4. Summary of what was updated (added, rewritten, removed, skipped).
5. Final changelog section content.
