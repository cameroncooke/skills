# Classification rubric

Use this rubric when auditing PR feedback. Classify based on repository evidence, not reviewer authority.

## Labels

### `valid`
- Comment correctly identifies a defect, risk, or policy violation.
- A concrete fix is required and in-scope.
- The concern may be line-anchored, or non-inline but still specific enough to verify through targeted code reading, or phrased as a question whose answer reveals a real defect or risk.
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
- Relevant file(s) and line references where available
- Behavior impact (what breaks or improves)
- Risk analysis (correctness, performance, readability, security)
- Why the proposed resolution is the best scoped outcome
- For non-inline feedback, name the code path(s) you inspected and why they were the right places to verify the concern
- For inline feedback, anchor the evidence to the review thread location and nearby diff unless the code path requires a small directly related expansion
- For question-style items, answer the question directly before explaining the supporting evidence
- For `valid` items, identify the defect pattern clearly and include evidence for any additional same-pattern instances you verified in the related changed PR surface
- Keep the evidence scoped to the same defect class and related changed PR surface; do not use it to justify unrelated cleanup, refactors, or different issue classes

## Bias guardrails

- Do not default to "valid" because a senior reviewer wrote it.
- Do not default to "invalid" because feedback is inconvenient.
- Verify by reading code paths and tests directly.
- Do not skip a comment just because it lacks an exact file or line reference.
- Do not treat broad or non-inline feedback as lower-confidence by default.
- Do not use one valid comment as justification to widen the change beyond the same defect class and related changed PR surface.
- If uncertain, mark as `contentious` and ask one focused user question.
