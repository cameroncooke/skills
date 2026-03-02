---
name: reconcile-merge-conflicts
description: Reconcile merge or rebase conflicts with branch-aware, regression-focused analysis. Use when asked to "resolve merge conflicts", "fix rebase conflicts", "reconcile conflicts", "rebase main", or "help me finish this merge". Detects active conflict state, guides branch selection when no operation is active, and produces a confidence-ranked reconciliation report with open questions. Treats the target branch (often `main`) as canonical for current behavior.
---

Resolve merge and rebase conflicts by preserving intent from both sides while preventing regressions.

Safety rules:

- Allow local git edits needed for reconciliation.
- Allow remote read-only git/GitHub operations (`fetch`, logs, PR metadata reads).
- Never run `git push`.
- Never run any `git reset` variant.

## Step 1: Detect operation state and workspace safety

Run:

```bash
git status --porcelain=v1 -b
git status
```

Classify state:

- **Active conflict state**: unmerged paths exist, or git reports in-progress merge/rebase.
- **No active conflict state**: no unmerged paths and no in-progress operation.

If git is unavailable or the directory is not a git repo, stop and report the failure.

If no operation is active and the working tree is dirty, stop and ask user to:

1. Commit current work, or
2. Stash current work, or
3. Clean branch manually.

Do not start merge/rebase on a dirty tree.

If an operation is already active, optionally create an in-progress safety bookmark (with user confirmation):

```bash
git branch backup/conflict-reconcile/inprogress/$(git rev-parse --short HEAD)
```

## Step 2: If no active conflict state, ask what to start

Ask user whether to:

- rebase onto branch (example: `rebase main`)
- merge branch (example: `merge main`)

Confirm current branch and intended direction first:

```bash
git branch --show-current
```

If current branch is not the intended source branch, stop and ask user to switch.

Before starting, create rollback branch:

```bash
git branch backup/conflict-reconcile/$(date +%Y%m%d-%H%M%S)-$(git rev-parse --short HEAD)
```

Tell user the backup branch name and recovery command:

```bash
git switch <backup-branch-name>
```

If backup branch name already exists, append a unique suffix and retry.

List all skill-created backups with:

```bash
git branch --list 'backup/conflict-reconcile/*'
```

Determine remote first (prefer `origin` if present, otherwise use the remote user specifies):

```bash
git remote
```

If user says rebase onto target branch, prefer up-to-date remote-tracking ref and capture evidence first:

```bash
git fetch <remote> <target-branch>
git rev-parse --short HEAD
git rev-parse --short <remote>/<target-branch>
git rebase <remote>/<target-branch>
```

Confirm target branch exists remotely before running. If `git rev-parse --short <remote>/<target-branch>` fails, stop and ask user to confirm the correct target branch name/remote.

Rebasing rewrites history. If branch is pushed/shared, ask for explicit confirmation before rebasing.

If user asks to merge target branch, prefer up-to-date remote-tracking ref and capture evidence first:

```bash
git fetch <remote> <target-branch>
git rev-parse --short HEAD
git rev-parse --short <remote>/<target-branch>
git merge <remote>/<target-branch>
```

Confirm target branch exists remotely before running. If user explicitly wants a local ref, follow user instruction.

## Step 3: Build conflict context before editing

Run:

```bash
git diff --name-only --diff-filter=U
git log --oneline --decorate --max-count=30
```

For each conflicted file, inspect both sides, merge-base version, recent commits, and related PR discussion when available.

Useful commands:

```bash
# stage 1 (base), stage 2 (ours), stage 3 (theirs)
git show :1:<path>
git show :2:<path>
git show :3:<path>
```

Use temporal signals as evidence, not proof.

Read `<skill-dir>/references/decision-rubric.md` for ambiguous choices.

## Step 4: Reconcile conflicts file-by-file

Default strategy:

1. Treat both sides as important.
2. Treat the target branch (often `main`) as canonical for current behavior.
3. Recreate source-branch intent on top of target-branch structure.
4. Avoid blind "take ours" / "take theirs" unless evidence is strong.

Prefer clean rewrites over marker patching when clearer or safer.

If source-side logic is obsolete, remove it and state evidence.

After each file resolution:

```bash
git add <file>
```

Continue operation:

- `git rebase --continue`
- for merges: `git commit --no-edit` (or `git merge --continue` when supported)

Repeat until no conflicts remain.

Before each continue/commit, verify no leftover conflict markers:

```bash
git diff --check
git grep -n '<<<<<<<\|>>>>>>>\|=======' -- .
```

## Step 5: Run quality gates before commit-producing steps and at end

Before each commit-producing continuation step (especially `git rebase --continue`), run fast high-signal checks. If checks fail, stop and fix.

After all conflicts are resolved, run the full quality gate set.

Read `<skill-dir>/references/quality-gates.md` for command discovery and precedence.

Never claim checks passed unless actually run.

## Step 6: Human review and rollback policy

Default to end-of-operation review:

1. complete reconciliation
2. run full quality gates
3. present final diff and audit report

Request mid-operation review only for high-risk areas or low confidence.

If any **Low-confidence** decision remains, require explicit human approval before finalizing.

Rollback options:

- active rebase: `git rebase --abort`
- active merge: `git merge --abort` (when available)
- post-operation: recover via backup branch from Step 2

Do not run destructive rollback commands automatically.

## Step 7: Produce reconciliation audit report

Include:

1. Summary (operation, target branch, files reconciled)
2. Per-file decisions (final structure side, preserved intent, rationale, regression risk)
3. Confidence-ranked decisions (High/Medium/Low)
4. Risks and follow-up checks
5. Open questions by change
6. Consolidated open-question list (repeat all questions)
7. Audit evidence block with:
   - command run
   - timestamp
   - resolved target commit hash
   - confidence level
   - attribution caveat

The target commit hash must come from explicit remote-tracking ref resolution (for example `git rev-parse <remote>/<target-branch>`), not from `FETCH_HEAD`.

Attribution rule:

- Reflog proves operation sequence and repo state transitions.
- Reflog does not prove actor identity. Do not claim it does.

## Output example

```markdown
## Reconciliation Audit

### Summary
- Operation: rebase onto `main`
- Conflicted files: 3
- Status: rebase completed

### Confidence-ranked decisions
- High — `src/core/parser.ts`: Kept new validation flow from main and reapplied source telemetry hook.
- Medium — `src/ui/filters.tsx`: Rewrote filter composition to preserve both behaviors.
- Low — `src/legacy/adapter.ts`: Removed source fallback path; needs owner confirmation.

### Audit evidence
- Command: `git rebase origin/main`
- Timestamp (UTC): `2026-03-02T11:15:34Z`
- Target hash: `13eeb846`
- Confidence: High
- Attribution caveat: reflog confirms operation sequence, not actor identity

### Open questions (consolidated)
1. Should legacy empty-state behavior remain for anonymous users?
2. Is external consumer `X` still relying on removed fallback behavior?
```

## Validation and exit criteria

Complete only when all are true:

- No conflicted files remain.
- Operation is complete or paused with clear next command.
- Preserved intent from both sides where applicable.
- Discarded logic has explicit evidence.
- Quality gates ran before commit-producing steps and after reconciliation, or gaps were reported.
- End-of-operation review was requested unless user opted out.
- If any Low-confidence decisions exist, explicit human approval was requested.
- Rollback path was communicated without `git reset`.
- No `git push` or `git reset` command was run.
