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

## Step 2: Audit comments without reviewer bias

Use `issue_comments` and `review_threads` from the JSON output as primary inputs. `reviews` is empty by default unless `--include-review-summaries` is used.

For each comment/thread:
1. Restate the concern briefly.
2. Verify in code/diff/tests directly.
3. Classify as one of:
   - `valid`
   - `invalid`
   - `contentious`
   - `already-addressed`
   - `out-of-scope`
4. Provide evidence and rationale.
5. Propose one best fix (or two options only if truly contentious).

For each audited item, include all of the following in the user-facing report:
- **Original report**: short verbatim quote from the comment body (or explicitly say “no actionable content”).
- **Concern restated**: one plain-language sentence.
- **Classification**: `valid|invalid|contentious|already-addressed|out-of-scope`.
- **Evidence**: concrete references with `path:line` plus short code snippets when relevant.
- **Resolution**: exact action (`no change`, `code change`, `docs change`, `follow-up PR`).
- **Scope/side effects**: one short note.

Do not return shallow summaries. Make the rationale specific enough that a reviewer can verify the decision quickly.

## Step 3: Ask approval before editing

Present a concise plan:
- comment link/id
- classification
- rationale
- exact proposed change
- expected side effects/scope

Do not edit code before explicit user approval.

Use this response shape:

```text
<one-line context: skill + PR>

1) <item type + id/link>
- Original report: "<short verbatim excerpt>"
- Concern (restated): ...
- Classification: ...
- Evidence:
  - path/to/file.ts:123
    <short snippet>
  - path/to/test.ts:45
    <short snippet>
- Recommended resolution: ...
- Alternative (only if needed): ...
- Scope/side effects: ...
```

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
- `reply_review_comment`: `repo`, `pr_number`, `comment_id`, `body` (`comment_id` = `review_threads[].comments[].databaseId`)
- `resolve_thread`: `thread_id` (`review_threads[].id`)
- `create_issue_comment`: `repo`, `pr_number`, `body`

Collector-to-action mapping:
- `review_threads[].id` → `resolve_thread.thread_id`
- `review_threads[].comments[].databaseId` → `reply_review_comment.comment_id`

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
