---
name: release-tweet
description: Draft a release announcement tweet from a GitHub release. Use when asked to compose a tweet, draft a release announcement, or write social media copy for a new version/release.
---

# Release Tweet Skill

Compose a release announcement tweet from GitHub release notes. This skill fetches the release, summarises changes, identifies contributors, cross-references X/Twitter handles, and outputs composed text for review. It does NOT post the tweet.

## Workflow

### Step 1 — Fetch release notes

Determine the repository from the current working directory or user input.

If the user specifies a tag:

```
gh release view <tag> --repo <owner/repo>
```

If no tag is given, find the latest release:

```
gh release list --repo <owner/repo> --limit 1
```

Then fetch its body:

```
gh release view <tag> --repo <owner/repo>
```

Extract the release body markdown for processing.

### Step 2 — Summarise changes as tweet bullets

Parse the release markdown sections (Added, Changed, Fixed, Removed) and rewrite each item as a concise, outcome-focused bullet:

- One line per bullet
- Merge related items where possible
- Drop purely internal items that don't matter to end users
- Keep the list to a reasonable length for a tweet (aim for 5-10 bullets max)
- Use backticks for CLI commands, tool names, and code references
- Focus on what the user gains, not implementation details

### Step 3 — Identify external contributors

Scan release notes for attribution patterns like `by [@username](...)`.

Extract GitHub usernames, then determine the repo owner:

```
gh api repos/<owner>/<repo> --jq '.owner.login'
```

Filter out:
- The repo owner
- Bot accounts (e.g. `dependabot`, `github-actions`)

The remaining usernames are external contributors.

### Step 4 — Cross-reference X/Twitter handles

For each external contributor, run the multi-signal verification procedure documented in `references/handle-verification.md`.

Classify each result as **high confidence** or **low confidence**.

### Step 5 — Compose the tweet

Assemble the tweet using the template and rules in `references/tweet-format.md`.

## Output

Present two things to the user:

1. **The composed tweet text** — ready to copy and post
2. **A confidence table** — showing each contributor's GitHub handle, resolved X handle (if any), confidence level, and reasoning

Example confidence table:

| GitHub | X Handle | Confidence | Reasoning |
|--------|----------|------------|-----------|
| @alice | @alice_dev | High | GitHub `twitter_username` field set |
| @bob | bob_codes | Low | Same handle exists on X but no corroborating signals |
| @charlie | — | — | No X presence found |

The user reviews everything and posts manually.
