# Scoring Reference

## Acceptance score (per observation)

- +2 reviewer positive follow-up (or approval after comment)
- +1 thread resolved
- +1 author acknowledgement (`fixed`, `addressed`, etc.)
- +0.5 commit after comment timestamp
- -1 unresolved request-change signal on merged PR
- -2 explicit dispute / won't-fix language

Bands:
- High: >= 3.0
- Medium: >= 1.5 and < 3.0
- Low: < 1.5

If dispute is explicit and reviewer does not later confirm, treat as disputed.

## Candidate score (0-10)

- Support: 0-3 (distinct PR count, capped at 3)
- Acceptance: 1-3
- Severity: 0-2
- Generality: 0-2

Heuristic suggestions (non-authoritative):
- Rule suggestion: total >= 8, acceptance >= 2, support >= 2 PRs, not disputed
- Learning suggestion: total >= 5 and acceptance >= 2

The agent makes the final keep/drop decision for every candidate.
Candidates are pre-ranked hints, not final selections.
