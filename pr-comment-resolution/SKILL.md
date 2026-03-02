---
name: pr-comment-resolution
description: Audit and resolve GitHub pull request review comments with an evidence-based workflow. Use when asked to "address PR comments", "resolve review feedback", "handle inline comments", "reply to review threads", or "close out PR review notes".
---

Audit PR feedback independently, then (after user approval) implement and reply/resolve in GitHub.

Path rule: treat `<skill-dir>` as the directory containing this `SKILL.md`.

## Preconditions

- `gh` is installed and authenticated.
- `python3` 3.11+ is available.
- Run from repository root.

## Step 1: Collect PR feedback

Default command:

```bash
python3 <skill-dir>/scripts/collect_pr_feedback.py --pr 1234
```

If PR is not provided, the script will try branch-based detection. If detection is ambiguous or empty, ask the user for PR number/URL and rerun.

Read `<skill-dir>/references/classification-rubric.md` before auditing.

## Step 2: Audit each comment

Use `issue_comments` and `review_threads` from the JSON output as primary inputs. `reviews` is empty by default unless `--include-review-summaries` is used.

First, triage each comment/thread. Skip any that are clearly non-actionable:
- Comments authored by the PR author (own comments)
- Bot-generated metadata (CI status, preview links, install commands, changelog entries)
- Simple acknowledgements, emoji reactions, or "thanks" replies
- Comments that contain no code review feedback

Skipped items do not get a full audit — they appear only in the "Skipped" section of the report.

For each remaining comment/thread, perform a full audit:
1. Restate the concern briefly.
2. Verify in code/diff/tests directly.
3. Classify as one of:
   - `valid`
   - `invalid`
   - `contentious`
   - `already-addressed`
   - `out-of-scope`
4. Gather evidence — concrete file/line references and short code snippets.
5. Decide the best resolution (or two options only if truly contentious).

Do not return shallow summaries. Make the rationale specific enough that a reviewer can verify the decision quickly.

## Step 3: Present findings and ask approval

Do not edit code before explicit user approval. Present findings using this format:

````markdown
## PR Comment Audit — <repo>#<number>

<N> comments reviewed on **<pr_title>**

---

# <short title summarising the concern>

`<classification>` · <review thread | issue comment>

## What the reviewer said

> <feedback content only — preserve meaning, strip HTML/UI chrome, bot footers, and non-feedback metadata>

## Analysis

<Discussion-style paragraph(s) explaining what you found when you checked the code. Reference specific files and lines naturally in prose, e.g. "In `src/foo.ts:42`, the value is already validated before this point..." Include short inline code snippets where they help. State whether the concern is warranted and why.>

## Proposed resolution

<What to do and why. For `no change`, explain why no action is needed. For code/doc changes, describe the specific change clearly. Keep it brief — one or two sentences is fine.>

---

# <short title summarising the concern>

`<classification>` · <review thread | issue comment>

## What the reviewer said

> ...

## Analysis

...

## Proposed resolution

...

---

## Skipped (non-actionable)

- **<author>**: <short description of comment> — <reason skipped, e.g. "own comment", "bot preview link", "CI status update">
- ...

---

## Next steps

<N> item(s) need changes. If you approve, I will:
  1. <change 1>
  2. <change 2>
  3. Run quality checks, then come back for commit/push approval before posting GitHub replies
````

Formatting rules:
- Each item starts with a `#` heading that describes the concern in plain language.
- Classification and comment type go on one line directly under the heading using inline code + separator.
- Reviewer words always in blockquotes — clearly separated from agent analysis.
- Analysis reads like prose, not bullet lists. Weave file references into sentences naturally.
- Horizontal rules (`---`) separate items.
- When bot comments contain large HTML/autofix blocks, keep only the feedback-relevant text.

## Step 4: Implement approved fixes

Keep changes minimal and in scope.
Run relevant quality checks before proposing commit/push (for example: lint, format, type-check, build, tests for touched areas).
If no code changed, state that checks were not required.
Ask before commit/push.

## Step 5: Reply and resolve after push

After user approves commit/push and push succeeds:

1. Build an action JSON.
2. Include commit references in reply bodies (for example: `Fixed in abc1234`).
3. Dry-run first, then apply:

```bash
cat <<'JSON' | python3 <skill-dir>/scripts/apply_resolution_actions.py
[
  {
    "action": "reply_review_comment",
    "repo": "owner/repo",
    "pr_number": 123,
    "comment_id": 456789,
    "body": "Fixed in abc1234."
  }
]
JSON
```

```bash
cat <<'JSON' | python3 <skill-dir>/scripts/apply_resolution_actions.py --apply
[
  {
    "action": "reply_review_comment",
    "repo": "owner/repo",
    "pr_number": 123,
    "comment_id": 456789,
    "body": "Fixed in abc1234."
  }
]
JSON
```

Action requirements:
- `reply_review_comment`: `repo`, `pr_number`, `comment_id`, `body` (REST endpoint — publishes immediately, no pending review)
- `resolve_thread`: `thread_id` (GraphQL node ID)
- `create_issue_comment`: `repo`, `pr_number`, `body`

Collector-to-action mapping:
- `review_threads[].comments[0].databaseId` → `reply_review_comment.comment_id` (must be the **first** comment in the thread — replies to replies are not supported by the GitHub API)
- `review_threads[].id` → `resolve_thread.thread_id`

Never claim a thread is resolved unless the resolve action succeeds.
Only resolve a thread when the concern is actually addressed in code (or reviewer/user explicitly agrees).
Do not resolve `contentious`, `invalid`, or `out-of-scope` items by default.

## Optional flags (only when needed)

`collect_pr_feedback.py`:
- `--include-resolved-threads`
- `--include-review-summaries`
- `--exclude-outdated-threads`
- `--exclude-bot-comments`
- `--view counts|bodies|thread-locations`

Examples:

```bash
python3 <skill-dir>/scripts/collect_pr_feedback.py --pr 1234 --view counts
python3 <skill-dir>/scripts/collect_pr_feedback.py --pr 1234 --view bodies
python3 <skill-dir>/scripts/collect_pr_feedback.py --pr 1234 --view thread-locations
```
