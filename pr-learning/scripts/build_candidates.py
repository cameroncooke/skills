#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import (
    ACK_PHRASES,
    DISPUTE_PHRASES,
    POSITIVE_REVIEWER_PHRASES,
    canonicalize_text,
    contains_any,
    first_sentence,
    hamming_distance,
    informative_tokens,
    now_iso,
    parse_pr_learning_signatures,
    read_json,
    sha256_hex,
    simhash64,
    write_json,
)

TOPIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("security", ("auth", "token", "secret", "xss", "csrf", "injection", "permission", "privacy", "secure")),
    ("correctness", ("bug", "incorrect", "wrong", "edge case", "null", "nil", "undefined", "exception", "crash")),
    ("performance", ("slow", "perf", "performance", "n+1", "cache", "latency", "memory", "cpu")),
    ("testing", ("test", "coverage", "regression", "flaky", "spec")),
    ("api-design", ("api", "contract", "breaking", "version", "public", "interface")),
    ("docs", ("docs", "readme", "documentation", "comment")),
    ("readability", ("readability", "clear", "clarity", "naming", "rename", "understand")),
    ("style", ("nit", "style", "format", "lint", "whitespace", "semicolon")),
]
SEVERITY_BY_TOPIC = {
    "security": "high",
    "correctness": "high",
    "performance": "medium",
    "api-design": "medium",
    "testing": "medium",
    "docs": "low",
    "readability": "low",
    "style": "low",
    "process": "medium",
    "other": "low",
}
ACCEPTANCE_THRESHOLD_HIGH = 3.0
ACCEPTANCE_THRESHOLD_MEDIUM = 1.5
FUZZY_DUPLICATE_HAMMING_THRESHOLD = 3
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ranked rule/learning candidates from PR feedback.")
    parser.add_argument("--input", default=".pr-learning/raw/feedback.json", help="Feedback JSON from collect_feedback.py")
    parser.add_argument("--output-dir", default=".pr-learning/analysis", help="Output directory for analysis artifacts")
    parser.add_argument("--project-store", default=".pr-learning/store.v1.json", help="Project dedupe store path")
    parser.add_argument("--tool", choices=["codex", "claude"], default="codex", help="Choose user store root")
    parser.add_argument("--user-store", help="Optional custom user store path")
    parser.add_argument("--allow-truncated-input", action="store_true", help="Allow analysis of truncated feedback input")
    return parser.parse_args()

def resolve_user_store(tool: str, explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser()
    base = Path.home() / (".codex" if tool == "codex" else ".claude")
    return base / "pr-learning" / "store.v1.json"

def parse_iso(ts: str | None) -> datetime:
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def classify_topic(text: str) -> str:
    lower = text.lower()
    for topic, words in TOPIC_KEYWORDS:
        if any(word in lower for word in words):
            return topic
    return "other"


def classify_intent(text: str) -> str:
    lower = text.lower()
    if "nit" in lower:
        return "nit"
    if "?" in lower and not any(w in lower for w in ("should", "must", "please", "prefer")):
        return "question"
    if any(w in lower for w in ("must", "need to", "should", "please", "avoid", "prefer", "use")):
        return "request-change"
    return "suggestion"


def infer_specificity(principle: str, path: str | None, files: list[str]) -> float:
    score = 0.0
    if path:
        score += 0.45
    if "/" in principle or re.search(r"\b[a-zA-Z0-9_\-]+\.[a-z]{2,5}\b", principle):
        score += 0.35
    basenames = {Path(f).name.lower() for f in files}
    if any(name and name in principle.lower() for name in basenames):
        score += 0.2
    return min(score, 1.0)


def proposed_text_from_seed(seed: str, candidate_type: str) -> str:
    cleaned = re.sub(r"\s+", " ", seed).strip().rstrip(".")
    cleaned = re.sub(r"^consider this pattern in similar changes:?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^in similar changes,?\s*", "", cleaned, flags=re.IGNORECASE)

    prefer_match = re.search(r"prefer\s+(.+?)\s+over\s+(.+)$", cleaned, re.IGNORECASE)
    if prefer_match:
        return f"Prefer {prefer_match.group(1).strip()} over {prefer_match.group(2).strip()}."

    instead_match = re.search(r"use\s+(.+?)\s+instead of\s+(.+)$", cleaned, re.IGNORECASE)
    if instead_match:
        return f"Use {instead_match.group(1).strip()} instead of {instead_match.group(2).strip()}."

    lead = cleaned[:1].upper() + cleaned[1:] if cleaned else "Use accepted review guidance"
    return lead + "."


def load_existing_signatures(project_store_path: Path, user_store_path: Path) -> tuple[set[str], set[str]]:
    semantic_keys: set[str] = set()
    fuzzy_keys: set[str] = set()
    for store_path in (project_store_path, user_store_path):
        data = read_json(store_path, default={})
        for item in data.get("codified", []):
            dedupe = item.get("dedupe", {})
            semantic_key = dedupe.get("semantic_key")
            fuzzy_key = dedupe.get("fuzzy_key")
            if semantic_key:
                semantic_keys.add(semantic_key)
            if fuzzy_key:
                fuzzy_keys.add(fuzzy_key)
    for doc_name in ("AGENTS.md", "CLAUDE.md"):
        path = Path(doc_name)
        if path.exists():
            file_semantic, file_fuzzy = parse_pr_learning_signatures(path.read_text())
            semantic_keys.update(file_semantic)
            fuzzy_keys.update(file_fuzzy)
    return semantic_keys, fuzzy_keys


def acceptance_from_thread(
    thread: dict[str, Any],
    comments: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    commits: list[dict[str, Any]],
    pr_state: str,
    intent: str,
    pr_author: str,
) -> dict[str, Any]:
    first_time = parse_iso(comments[0].get("createdAt"))
    author_replies = [c for c in comments[1:] if ((c.get("author") or {}).get("login") or "") == pr_author]
    reviewer_replies = [c for c in comments[1:] if ((c.get("author") or {}).get("login") or "") not in {"", pr_author}]

    author_ack = any(contains_any(c.get("body", ""), ACK_PHRASES) for c in author_replies)
    author_dispute = any(contains_any(c.get("body", ""), DISPUTE_PHRASES) for c in author_replies)
    reviewer_positive = any(contains_any(c.get("body", ""), POSITIVE_REVIEWER_PHRASES) for c in reviewer_replies)
    reviewer_positive = reviewer_positive or any(
        (review.get("state") == "APPROVED") and parse_iso(review.get("submittedAt")) > first_time
        for review in reviews
    )
    commit_after = any(parse_iso(commit.get("committedDate")) > first_time for commit in commits)

    score = 0.0
    if reviewer_positive:
        score += 2.0
    if thread.get("isResolved"):
        score += 1.0
    if author_ack:
        score += 1.0
    if commit_after:
        score += 0.5
    if intent == "request-change" and pr_state == "MERGED" and not thread.get("isResolved"):
        score -= 1.0
    if author_dispute:
        score -= 2.0

    if author_dispute and not reviewer_positive:
        outcome = "disputed"
    elif score >= ACCEPTANCE_THRESHOLD_HIGH:
        outcome = "accepted"
    elif score >= ACCEPTANCE_THRESHOLD_MEDIUM:
        outcome = "partially"
    elif author_dispute:
        outcome = "wontfix"
    else:
        outcome = "unclear"

    band = "high" if score >= ACCEPTANCE_THRESHOLD_HIGH else "medium" if score >= ACCEPTANCE_THRESHOLD_MEDIUM else "low"
    return {
        "author_ack": author_ack,
        "author_dispute": author_dispute,
        "reviewer_positive": reviewer_positive,
        "commit_after": commit_after,
        "score": score,
        "band": band,
        "outcome": outcome,
    }


def collect_observations(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    pr = bundle["pr"]
    pr_author = pr.get("author") or ""
    files = bundle.get("files", [])
    commits = bundle.get("commits", [])
    reviews = bundle.get("reviews", [])
    observations: list[dict[str, Any]] = []

    for thread in bundle.get("review_threads", []):
        comments = thread.get("comments", {}).get("nodes", [])
        if not comments:
            continue
        first_body = comments[0].get("body") or ""
        if not first_body.strip():
            continue
        first_author = (comments[0].get("author") or {}).get("login") or ""
        if first_author == pr_author:
            continue

        topic = classify_topic(first_body)
        intent = classify_intent(first_body)
        action_summary = first_sentence(first_body, fallback="Review feedback")
        principle = first_sentence(first_body).rstrip(".")[:220]
        acceptance = acceptance_from_thread(thread, comments, reviews, commits, pr.get("state", ""), intent, pr_author)
        patch_excerpt = ((bundle.get("file_patches") or {}).get(thread.get("path") or "") or "")[:1200]

        tokens = informative_tokens(canonicalize_text(principle))
        if not tokens:
            continue
        semantic_key = sha256_hex(f"{topic}|{' '.join(tokens[:12])}")
        path = thread.get("path")
        specificity = infer_specificity(principle, path, files)

        observations.append(
            {
                "observation_id": sha256_hex(f"{pr['url']}|{thread.get('id')}|{semantic_key}"),
                "repo": pr.get("url", "").split("/pull/")[0].replace("https://github.com/", ""),
                "pr_number": pr["number"],
                "thread_id": thread.get("id"),
                "path": path,
                "line": thread.get("line"),
                "topic": topic,
                "severity": SEVERITY_BY_TOPIC.get(topic, "low"),
                "intent": intent,
                "action_summary": action_summary,
                "principle": principle,
                "evidence": {
                    "thread_resolved": bool(thread.get("isResolved")),
                    "author_acknowledged": acceptance["author_ack"],
                    "author_disputed": acceptance["author_dispute"],
                    "reviewer_positive": acceptance["reviewer_positive"],
                    "commit_after_comment": acceptance["commit_after"],
                    "merge_state": pr.get("state"),
                },
                "acceptance_score": acceptance["score"],
                "acceptance_band": acceptance["band"],
                "outcome": acceptance["outcome"],
                "specificity": round(specificity, 3),
                "generality": round(1.0 - specificity, 3),
                "dedupe": {
                    "source_ids": [c.get("id") for c in comments if c.get("id")],
                    "semantic_key": semantic_key,
                    "fuzzy_key": simhash64(tokens),
                },
                "sources": [{"url": c.get("url"), "comment_id": c.get("id"), "created_at": c.get("createdAt")} for c in comments],
                "thread_transcript": [
                    {
                        "author": (c.get("author") or {}).get("login"),
                        "body": c.get("body"),
                        "url": c.get("url"),
                        "created_at": c.get("createdAt"),
                        "reply_to": (c.get("replyTo") or {}).get("id") if c.get("replyTo") else None,
                    }
                    for c in comments
                ],
                "code_context": {
                    "path": thread.get("path"),
                    "line": thread.get("line"),
                    "patch_excerpt": patch_excerpt,
                },
                "created_at": now_iso(),
            }
        )

    return observations


def acceptance_component(avg_acceptance: float, any_disputed: bool, any_high: bool) -> int:
    if avg_acceptance >= ACCEPTANCE_THRESHOLD_HIGH:
        base = 3
    elif avg_acceptance >= ACCEPTANCE_THRESHOLD_MEDIUM:
        base = 2
    else:
        base = 1
    return min(base, 1) if any_disputed and not any_high else base


def build_candidate(cluster: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    if not cluster:
        return None

    support_prs = sorted({obs["pr_number"] for obs in cluster})
    review_signal_count = sum(1 for obs in cluster if obs["evidence"]["reviewer_positive"])
    avg_acceptance = sum(obs["acceptance_score"] for obs in cluster) / len(cluster)
    any_disputed = any(obs["outcome"] in {"disputed", "wontfix"} for obs in cluster)
    any_high = any(obs["acceptance_band"] == "high" for obs in cluster)

    acc_comp = acceptance_component(avg_acceptance, any_disputed, any_high)
    sev_level = "high" if any(obs["severity"] == "high" for obs in cluster) else "medium" if any(obs["severity"] == "medium" for obs in cluster) else "low"
    sev_comp = 2 if sev_level == "high" else 1 if sev_level == "medium" else 0
    avg_generality = sum(obs["generality"] for obs in cluster) / len(cluster)
    avg_specificity = sum(obs["specificity"] for obs in cluster) / len(cluster)
    gen_comp = 2 if avg_generality >= 0.75 else 1 if avg_generality >= 0.4 else 0
    support_comp = min(3, len(support_prs))
    total = support_comp + acc_comp + sev_comp + gen_comp

    # Heuristic hints only. Agent performs final selection.
    if acc_comp < 2:
        return None

    type_suggestion = "learning"
    if total >= 8 and acc_comp >= 2 and len(support_prs) >= 2 and not any_disputed and review_signal_count >= 2 and avg_acceptance >= ACCEPTANCE_THRESHOLD_HIGH:
        type_suggestion = "rule"

    scope = "project"
    if (
        avg_generality >= 0.75
        and avg_specificity < 0.35
        and acc_comp >= 2
        and (len(support_prs) >= 3 or (len(support_prs) >= 2 and review_signal_count >= 2))
    ):
        scope = "user"

    confidence_band = "high" if avg_acceptance >= ACCEPTANCE_THRESHOLD_HIGH else "medium" if avg_acceptance >= ACCEPTANCE_THRESHOLD_MEDIUM else "low"
    representative = sorted(cluster, key=lambda obs: obs["acceptance_score"], reverse=True)[0]

    return {
        "id": f"C{index:03d}",
        "type": type_suggestion,
        "scope_suggestion": scope,
        "topic": representative["topic"],
        "severity": sev_level,
        "proposed_text": proposed_text_from_seed(representative["action_summary"], type_suggestion),
        "rationale": representative["principle"],
        "confidence": {
            "acceptance_average": round(avg_acceptance, 3),
            "band": confidence_band,
            "score_total": total,
            "components": {"support": support_comp, "acceptance": acc_comp, "severity": sev_comp, "generality": gen_comp},
        },
        "heuristic_hints": {
            "minimum_acceptance_gate_passed": acc_comp >= 2,
            "disputed_present": any_disputed,
            "type_suggestion_confidence": confidence_band,
            "likely_business_logic_specific": avg_specificity >= 0.7 and len(support_prs) == 1,
            "selection_authority": "agent",
        },
        "support": {
            "observation_count": len(cluster),
            "distinct_prs": support_prs,
            "review_signal_count": review_signal_count,
            "disputed_present": any_disputed,
        },
        "dedupe": representative["dedupe"],
        "source_refs": [{"pr_number": obs["pr_number"], "urls": [src.get("url") for src in obs["sources"] if src.get("url")]} for obs in cluster],
        "examples": [
            {
                "pr_number": obs["pr_number"],
                "summary": obs["action_summary"],
                "outcome": obs["outcome"],
                "topic": obs["topic"],
                "code_context": obs.get("code_context"),
                "thread_transcript": obs.get("thread_transcript"),
            }
            for obs in cluster[:3]
        ],
    }


def write_report(path: Path, repo: str, candidates: list[dict[str, Any]], duplicates: list[dict[str, Any]], observation_count: int) -> None:
    lines = [
        "# PR Learning Candidate Report",
        "",
        f"- Repo: `{repo}`",
        f"- Observations: {observation_count}",
        f"- Candidates: {len(candidates)}",
        f"- Skipped as duplicates: {len(duplicates)}",
        "",
        "## Candidates",
        "",
    ]
    if not candidates:
        lines.append("No candidate rules/learnings generated.")
    else:
        for candidate in candidates:
            lines.extend(
                [
                    f"### {candidate['id']} — {candidate['type']} ({candidate['scope_suggestion']})",
                    f"- Text: {candidate['proposed_text']}",
                    f"- Topic: {candidate['topic']} | Severity: {candidate['severity']}",
                    f"- Confidence: {candidate['confidence']['band']} ({candidate['confidence']['acceptance_average']})",
                    f"- Support PRs: {', '.join(map(str, candidate['support']['distinct_prs']))}",
                    "",
                ]
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def find_probable_fuzzy_duplicate(fuzzy_key: str, fuzzy_keys: set[str]) -> tuple[str | None, int | None]:
    for existing in fuzzy_keys:
        try:
            distance = hamming_distance(fuzzy_key, existing)
        except ValueError:
            continue
        if distance <= FUZZY_DUPLICATE_HAMMING_THRESHOLD:
            return existing, distance
    return None, None

def main() -> None:
    args = parse_args()
    payload = read_json(Path(args.input), default={})
    if not payload:
        raise SystemExit(f"Input file not found or empty: {args.input}")
    input_truncated = bool(payload.get("truncated"))
    if input_truncated and not args.allow_truncated_input:
        raise SystemExit("Input feedback is truncated. Re-run collect_feedback.py without truncation or pass --allow-truncated-input.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    project_store = Path(args.project_store)
    user_store = resolve_user_store(args.tool, args.user_store)
    existing_semantic, existing_fuzzy = load_existing_signatures(project_store, user_store)

    all_observations: list[dict[str, Any]] = []
    for bundle in payload.get("prs", []):
        all_observations.extend(collect_observations(bundle))

    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    duplicates: list[dict[str, Any]] = []
    for observation in all_observations:
        semantic_key = observation["dedupe"]["semantic_key"]
        fuzzy_key = observation["dedupe"]["fuzzy_key"]
        if semantic_key in existing_semantic:
            duplicates.append({"observation_id": observation["observation_id"], "semantic_key": semantic_key, "reason": "already_codified", "pr_number": observation["pr_number"]})
            continue
        fuzzy_match, distance = find_probable_fuzzy_duplicate(fuzzy_key, existing_fuzzy)
        if fuzzy_match:
            duplicates.append(
                {
                    "observation_id": observation["observation_id"],
                    "semantic_key": semantic_key,
                    "fuzzy_key": fuzzy_key,
                    "matched_fuzzy_key": fuzzy_match,
                    "hamming_distance": distance,
                    "reason": "probable_duplicate",
                    "pr_number": observation["pr_number"],
                }
            )
            continue
        clusters[semantic_key].append(observation)

    candidates: list[dict[str, Any]] = []
    for idx, cluster in enumerate(sorted(clusters.values(), key=len, reverse=True), start=1):
        candidate = build_candidate(cluster, idx)
        if not candidate:
            continue
        if input_truncated:
            if candidate["type"] == "rule":
                candidate["type"] = "learning"
            candidate["scope_suggestion"] = "project"
        candidates.append(candidate)

    write_json(output_dir / "observations.json", {"generated_at": now_iso(), "observations": all_observations})
    write_json(
        output_dir / "candidates.json",
        {
            "generated_at": now_iso(),
            "repo": payload.get("repo"),
            "query": payload.get("query"),
            "tool": args.tool,
            "project_store": str(project_store),
            "user_store": str(user_store),
            "candidate_count": len(candidates),
            "candidates": candidates,
        },
    )
    write_json(output_dir / "duplicates.json", {"generated_at": now_iso(), "duplicates": duplicates})
    write_report(output_dir / "report.md", payload.get("repo", "unknown"), candidates, duplicates, len(all_observations))

    print(f"Observations: {len(all_observations)}")
    print(f"Candidates: {len(candidates)}")
    print(f"Duplicates skipped: {len(duplicates)}")
    print(f"Artifacts written to: {output_dir}")


if __name__ == "__main__":
    main()
