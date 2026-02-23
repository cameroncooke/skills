# Tweet Format Reference

## Template

```
<Project> <version> is out!

<Optional intro line>

<Bullet list of changes>

<Install/upgrade reminder>

<Contributor shout-out>
```

## Rules

### Title line
- Format: `<Project> <version> is out!`
- Example: `XcodeBuildMCP v2.1.0 is out!`

### Intro line (optional)
- A short phrase setting context when warranted (e.g. "Big update!:" or "Lots of improvements:")
- Omit if the bullet list speaks for itself

### Bullet list
- Each bullet is concise and outcome-focused
- Use backticks for CLI commands, tool names, and code references
- Start each bullet with an emoji-free dash or bullet character
- Keep to 5-10 bullets maximum

### Install/upgrade reminder
- Include only if there's a standard install/upgrade path
- Example: `brew install xcodebuildmcp` or `npm update <package>`
- Omit if no obvious install command exists

### Contributor shout-out
- Format: "Shout out to @handle1, @handle2, and @handle3 for their contributions!"
- High-confidence contributors: use `@handle` (their X/Twitter handle)
- Low-confidence contributors: use their plain text name or GitHub username without `@`
- If no external contributors, omit this section entirely

### Tone
- Enthusiastic but professional
- No marketing fluff or hyperbole
- No hashtags unless the user specifically requests them
- Direct and informative
