# My Skills

A collection of custom Agent skills.

## Included Skills

- `changelog-updater` - Update upcoming `CHANGELOG` release notes with user-facing outcomes, including canonical prerelease handling (for example, `v2.0.0-beta.1` -> `2.0.0` section).
- `pr-learning` - Mine PR review feedback into ranked rule/learning candidates and codify approved items into AGENTS.md/CLAUDE.md with dedupe + provenance.
- `release-tweet` - Draft a release announcement tweet from a GitHub release, summarising changes, identifying contributors, and cross-referencing X/Twitter handles.
- `agent-change-walkthrough` - Generate a single-story implementation walkthrough of AI-authored changes, ordered by dependency then runtime flow, with `path/to/file:line` snippet headers, annotated diffs, concrete input/output examples, trade-offs, and risks.

## Usage

Skills can be installed by copying them to:
- Claude Code: `~/.claude/skills/`
- Codex: `~/.codex/skills/public/`
