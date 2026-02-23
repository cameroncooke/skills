#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "i", "if", "in", "into", "is", "it", "its", "of", "on", "or", "that",
    "the", "their", "then", "there", "these", "this", "to", "was", "we", "were",
    "will", "with", "you", "your", "our", "can", "should", "could", "would",
}

ACK_PHRASES = (
    "fixed", "addressed", "done", "updated", "good catch", "agree", "makes sense",
)
DISPUTE_PHRASES = (
    "disagree",
    "won't fix",
    "wont fix",
    "not necessary",
    "by design",
    "prefer not to",
    "already supported",
    "already handled",
    "already does",
    "out of date",
    "stale feedback",
)
POSITIVE_REVIEWER_PHRASES = (
    "lgtm", "looks good", "approved", "ship it", "good to merge",
)


def run_command(args: list[str], stdin_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        input=stdin_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stderr.strip()}"
        )
    return result.stdout


def run_gh_json(args: list[str], stdin_text: str | None = None) -> Any:
    raw = run_command(["gh", *args], stdin_text=stdin_text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse gh JSON output: {exc}\nOutput snippet: {raw[:400]}") from exc


def run_gh_graphql(query: str, variables: dict[str, Any]) -> Any:
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if isinstance(value, bool):
            args.extend(["-F", f"{key}={'true' if value else 'false'}"])
        elif isinstance(value, int):
            args.extend(["-F", f"{key}={value}"])
        else:
            args.extend(["-f", f"{key}={value}"])
    payload = run_gh_json(args)
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def strip_markdown(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`[^`]+`", " <code> ", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = text.replace("\r", " ")
    return text


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def canonicalize_text(text: str) -> str:
    text = strip_markdown(text).lower()
    text = re.sub(r"\b\d+(?:\.\d+)*\b", " <num> ", text)
    text = re.sub(r"[^a-z0-9_\-/<code>\s]", " ", text)
    return normalize_whitespace(text)


def informative_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9_\-]+", text)
    return [t for t in tokens if len(t) > 2 and t not in STOP_WORDS]


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def simhash64(tokens: list[str]) -> str:
    if not tokens:
        return "0x0"
    bits = [0] * 64
    for token in tokens:
        h = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:16], 16)
        for idx in range(64):
            bits[idx] += 1 if ((h >> idx) & 1) else -1
    out = 0
    for idx, value in enumerate(bits):
        if value >= 0:
            out |= 1 << idx
    return f"0x{out:016x}"


def hamming_distance(a_hex: str, b_hex: str) -> int:
    a = int(a_hex, 16)
    b = int(b_hex, 16)
    return (a ^ b).bit_count()


def first_sentence(text: str, fallback: str = "") -> str:
    cleaned = normalize_whitespace(strip_markdown(text))
    if not cleaned:
        return fallback
    match = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)
    return match[0][:240]


def contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    hay = text.lower()
    return any(phrase in hay for phrase in phrases)


def parse_pr_learning_signatures(markdown_text: str) -> tuple[set[str], set[str]]:
    keys: set[str] = set()
    sims: set[str] = set()

    for match in re.finditer(r"pr-learning:v=1[^>]*key=([^\s;]+)", markdown_text):
        keys.add(match.group(1))
    for match in re.finditer(r"pr-learning:v=1[^>]*sim=([^\s;]+)", markdown_text):
        sims.add(match.group(1))

    return keys, sims


def parse_pr_learning_keys(markdown_text: str) -> set[str]:
    keys, _ = parse_pr_learning_signatures(markdown_text)
    return keys
