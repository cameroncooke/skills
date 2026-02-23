# Dedupe Reference

Use three dedupe layers:

1. Source IDs (comment/thread IDs)
2. Semantic key (`sha256(topic + canonical principle tokens)`)
3. Fuzzy key (`simhash64(tokens)`)

Codified bullets include provenance metadata:

```md
<!-- pr-learning:v=1 type=rule scope=project key=<semantic> sim=<fuzzy> sources=PR#12 confidence=0.82 -->
```

Before generating new candidates, check:
- project store (`.pr-learning/store.v1.json`)
- user store (`~/.codex/pr-learning/store.v1.json`)
- existing AGENTS.md / CLAUDE.md metadata comments
