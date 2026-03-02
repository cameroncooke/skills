# Agent Instructions

## Skills
- Use `skill-creator` when creating or updating skills.
- See `/Users/cameroncooke/.agents/skills/skill-creator/SKILL.md`.

## Skill Validation
- After any change to a skill (`SKILL.md`, `references/`, `scripts/`, `assets/`), run:
```bash
npx skill-check
```
- Also validate the changed skill with skills-ref:
```bash
skills-ref validate <path-to-skill>
```
- If `skills-ref` is not installed, run via uvx:
```bash
uvx --from skills-ref agentskills validate <path-to-skill>
```
- Fix all issues reported by validation tools before finishing.

## Package Manager
- No repo package manager is required for skill authoring.
- Use `npx` for skill checks and `uv run` for Python-based validators.

## Commit Attribution
- Follow repository/user commit attribution requirements when committing.
