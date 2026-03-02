# Decision Rubric

Use this rubric when conflict choices are ambiguous.

Terminology: "target branch" means the branch you are rebasing onto or merging into (often `main`).

## Signals and default actions

| Signal | Interpretation | Default action |
|---|---|---|
| Target-branch commit is recent and reviewed | High confidence target-branch behavior is intentional | Keep target-branch behavior; reapply source intent carefully |
| Source commit is recent and conflicts with older main code | Source may contain newer product intent | Preserve source intent while keeping current architecture stable |
| Both sides refactor same area | Dual intent with structural conflict | Rewrite block to preserve behavior from both sides |
| One side is clearly dead code | Low value to retain | Remove dead code and explain evidence |

## Evidence hierarchy

Prefer stronger evidence first:

1. Passing tests tied to changed behavior
2. Explicit PR review/sign-off discussion
3. Recent commits with clear intent in message/diff
4. Local code comments and naming intent
5. Temporal recency alone (weakest; never sole justification)

## Confidence scoring guidance

- **High**: strong evidence and behavior validated
- **Medium**: partial evidence; low ambiguity remains
- **Low**: unresolved ambiguity, missing validation, or unclear ownership

If confidence is Low, ask explicit human approval before finalizing.
