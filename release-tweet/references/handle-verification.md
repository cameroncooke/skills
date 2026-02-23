# X/Twitter Handle Verification Procedure

For each external contributor identified from the release notes, run the following signals in order. Use all available signals before making a confidence determination.

## Signal 1 — GitHub `twitter_username` field

```
gh api users/<username> --jq '.twitter_username'
```

If this returns a non-null, non-empty value, this is the contributor's self-declared X handle. This is the strongest signal available.

## Signal 2 — Same-handle check

Search the web for `site:x.com/<github_username>` to determine whether an X account with the same handle exists.

If the account exists, note it as a candidate but do not assume it's the same person without corroboration.

## Signal 3 — Blog/website cross-reference

Fetch the contributor's GitHub profile fields:

```
gh api users/<username> --jq '{name: .name, blog: .blog, bio: .bio}'
```

If they have a blog or personal website, look for links to an X/Twitter profile on that site. If their real name appears on both the X profile and the GitHub profile, that's a corroborating signal.

## Signal 4 — Contextual fit

Check whether the candidate X account's bio, posts, or focus area aligns with the project's domain (e.g. iOS development, mobile tooling, Swift).

A mismatch (e.g. the X account is about cooking) is a strong negative signal.

## Confidence Classification

### High confidence
Assign **high confidence** when ANY of these conditions are met:
- GitHub `twitter_username` field is set (Signal 1)
- Multiple signals corroborate: same handle exists (Signal 2) AND contextual fit matches (Signal 4) AND website cross-reference confirms (Signal 3)

### Low confidence
Assign **low confidence** when:
- Only one weak signal is present (e.g. same handle exists but no corroboration)
- The X profile doesn't clearly match the contributor

### No match
If no signals produce a candidate, record the contributor with no X handle and skip them in the tweet's `@mention` list. Use their plain name or GitHub username instead.

## Output

For each contributor, record:
- GitHub username
- Resolved X handle (if any)
- Confidence level (high / low / none)
- Brief reasoning citing which signals were used
