---
name: pr-learning
description: Mine PR review feedback to extract repeatable rules/learnings, present ranked candidates, and codify approved items into AGENTS.md/CLAUDE.md with dedupe + provenance.
---

# PR Learning (Continuous Improvement from Review Feedback)

## Your role

You are a Staff Engineer turning PR feedback into durable team guidance.

You are not summarizing PRs. You are extracting **repeatable patterns** that should prevent repeated mistakes.

## What this skill does

1. Collect PR review artifacts (comments, threads, replies, commit context) using `gh`.
2. Normalize feedback into observations.
3. Score acceptance/dispute confidence.
4. Cluster repeated patterns.
5. Propose candidate **Rules** (strict) and **Learnings** (soft).
6. Ask the user to choose `all`, `none`, or selected IDs.
7. Codify approved candidates in project/user AGENTS.md or CLAUDE.md with provenance markers.
8. Persist dedupe state so the same lesson is not re-added.

## Preconditions

- `gh` is installed and authenticated (`gh auth status`).
- `python3` is available.
- Run scripts from the target repository root.

## Defaults and scope

- Default repository: current repo from `gh repo view`.
- Override repository: pass `--repo owner/repo`.
- Default PR search: PRs involving the authenticated user (`involves:<login>`) across open + closed states.
- Default window: **all-time by default** (`--since-days 0`) and max 200 PRs unless overridden.

## Safety invariants

1. **Never write AGENTS.md/CLAUDE.md before user selection.**
2. Always show candidate list with evidence first.
3. Dedupe against existing codified items and stored keys before proposing writes (semantic + fuzzy keys).
4. If feedback is disputed and not clearly resolved, do not promote to strict rule.
5. Bias scope to **project** unless genericity and repetition are clearly strong.
6. Scripts provide deterministic pre-ranking only; the agent performs final candidate selection with reasoning.

## Workflow

### Step 1: Collect feedback artifacts

```bash
python3 pr-learning/scripts/collect_feedback.py --since-days 0 --limit 200
```

`--since-days 0` means no date filtering (historical backfill mode).

If collection reports truncation due pagination, either narrow your query or explicitly accept partial data with `--allow-truncated`.

If discovery returns suspiciously few PRs, stop and widen discovery before candidate generation.

Useful flags:

```bash
python3 pr-learning/scripts/collect_feedback.py \
  --repo owner/repo \
  --since-days 120 \
  --limit 300 \
  --out .pr-learning/raw/feedback.json
```

### Step 2: Build observations and ranked candidates

```bash
python3 pr-learning/scripts/build_candidates.py \
  --input .pr-learning/raw/feedback.json \
  --output-dir .pr-learning/analysis
```

If input is intentionally partial, add `--allow-truncated-input`.

Outputs:

- `.pr-learning/analysis/observations.json`
- `.pr-learning/analysis/candidates.json`
- `.pr-learning/analysis/duplicates.json`
- `.pr-learning/analysis/report.md`

### Step 3: Agent shortlist (required before asking user)

Before showing options to the user, the agent must review `candidates.json` and classify every candidate as:
- `KEEP` (plausibly reusable guidance)
- `REJECT` (local/one-off/noise)

Only present `KEEP` candidates to the user. Never ask the user to choose from obvious `REJECT` items.

For each shortlisted (`KEEP`) candidate, include:
- ID + type/scope suggestion + confidence
- **Proposed text** (exact bullet that would be written)
- Why it passed shortlist (1 sentence)
- Evidence summary + source URLs + relevant thread/code context

Also include a brief filtered summary, e.g.:
- "Filtered out 4 candidates as one-off/local feedback (rename/move/nit/file-specific)."

Then ask:

- `all`
- `none`
- `C001,C004,C007` (specific IDs)

Optional: ask if the user wants wording edits before codification.

### Step 4: Codify approved items

Dry-run preview (default):

```bash
python3 pr-learning/scripts/codify_learnings.py \
  --candidates .pr-learning/analysis/candidates.json \
  --select C001,C004
```

Write changes:

```bash
python3 pr-learning/scripts/codify_learnings.py \
  --candidates .pr-learning/analysis/candidates.json \
  --select all \
  --write \
  --yes
```

## Acceptance/dispute model

Each observation gets an explainable acceptance score.

Positive signals:
- Reviewer positive follow-up/approval after feedback.
- Thread resolved.
- Author acknowledgement (e.g. "fixed", "addressed").
- Follow-up commit after comment.

Negative signals:
- Explicit dispute/won't-fix language.
- Unresolved request-change patterns that merged without clear follow-up.

If dispute is explicit and no later positive reviewer signal exists, treat as disputed.

## Selection rubric (default: reject)

The script output is a candidate pool, not final decisions. The agent should only present candidates to the user when they are likely reusable guidance.

Hard reject candidates when any apply:
- Pure one-off/local comments (rename this variable, move this helper, file-specific nit)
- Disputed feedback with no later confirmation
- Non-actionable phrasing
- Guidance tied to a single line/object with no forward scope
- Change request that only affects naming/layout without durable policy value
- Business-logic-specific feedback that only applies to one endpoint/feature/path and does not generalize

Accept as project-scope when all apply:
- Accepted signal is meaningful (not disputed)
- Actionable phrasing exists
- Likely reusable in other areas of the codebase
- Reads as a future rule, not as a PR-specific observation
- Not tightly coupled to one piece of business logic

Accept as user-scope only when clearly generic and broadly reusable across repositories.

Positive examples:
- "Prefer explicit errors over silent fallback behavior"
- "Use camelCase for TypeScript identifiers"

Reject examples:
- "skillLabel is identical to skillDirName"
- "rename foo to bar"
- "move this helper"
- "this variable name is redundant in this file"
- "swap this function call order in this one code path"
- "for this endpoint, apply business rule X before Y"

## Scope decision

- **Project scope** if feedback references project APIs, modules, paths, architecture, or local process.
- **User scope** only if pattern is generic, repeated, and accepted across multiple PRs/reviewers.

## Target file precedence

Project scope:
1. `./AGENTS.md` (if exists)
2. `./CLAUDE.md` (if AGENTS missing)
3. else create `./AGENTS.md`

User scope (Codex):
1. `~/.codex/AGENTS.md`
2. `~/.codex/CLAUDE.md`
3. else create `~/.codex/AGENTS.md`

User scope (Claude mode): same precedence under `~/.claude/`.

## Dedupe and provenance

Dedupe uses three layers:
1. Source IDs (exact comment/thread duplicates).
2. Semantic key (normalized principle hash).
3. Fuzzy key (simhash on normalized tokens).

Codified bullets include machine-readable provenance comments:

```md
- Prefer ?? over || for default values unless falsy values are intentionally treated as empty.
  <!-- pr-learning:v=1 type=rule scope=project key=... sim=... sources=PR#12,PR#44 confidence=0.88 -->
```

## Output contract

At the end, report:

1. Repo + query used.
2. PRs scanned and feedback artifacts parsed.
3. Candidate count by type (`rule`, `learning`).
4. Selected IDs and skipped duplicates.
5. Exact write targets.
6. Inserted bullet text.

## References

- `pr-learning/references/SCORING.md`
- `pr-learning/references/SCOPE_RULES.md`
- `pr-learning/references/DEDUPE.md`
- `pr-learning/assets/candidate.schema.json`
- `pr-learning/assets/store.schema.json`

## Notes

- `codify_learnings.py --write` requires `--yes`.
- `--tool codex|claude` controls user-level store and write targets.
