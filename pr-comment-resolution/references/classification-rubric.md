# Classification rubric

Use this rubric when auditing PR feedback. Classify based on repository evidence, not reviewer authority.

## Labels

### `valid`
- Comment correctly identifies a defect, risk, or policy violation.
- A concrete fix is required and in-scope.
- The concern is specific enough to verify the reported defect and to check the related changed PR surface for any same-pattern instances.

### `invalid`
- Comment is factually incorrect based on current code, architecture, or requirements.
- No code change should be made.

### `contentious`
- Comment highlights a real tradeoff but no single objectively correct answer exists.
- Present recommendation plus alternatives.

### `already-addressed`
- The concern is fixed in the current branch (or superseded by newer code).
- Reply with evidence and commit reference if available.

### `out-of-scope`
- Comment requests change outside PR goals or requires separate workstream.
- Recommend follow-up issue/PR, not opportunistic expansion.

## Evidence standards

For each decision, include:
- Relevant file(s) and line references
- Behavior impact (what breaks or improves)
- Risk analysis (correctness, performance, readability, security)
- Why the proposed resolution is the best scoped outcome
- For `valid` items, identify the defect pattern clearly and include evidence for any additional same-pattern instances you verified in the related changed PR surface
- Keep the evidence scoped to the same defect class and related changed PR surface; do not use it to justify unrelated cleanup, refactors, or different issue classes

## Bias guardrails

- Do not default to "valid" because a senior reviewer wrote it.
- Do not default to "invalid" because feedback is inconvenient.
- Verify by reading code paths and tests directly.
- Do not use one valid comment as justification to widen the change beyond the same defect class and related changed area.
- If uncertain, mark as `contentious` and ask one focused user question.
