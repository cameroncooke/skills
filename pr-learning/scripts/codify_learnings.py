#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from common import now_iso, parse_pr_learning_keys, read_json, sha256_hex, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codify selected PR learning candidates into AGENTS/CLAUDE docs.")
    parser.add_argument("--candidates", default=".pr-learning/analysis/candidates.json", help="candidates.json path")
    parser.add_argument(
        "--select",
        required=True,
        help="Selection: all | none | comma-separated candidate IDs (e.g. C001,C004)",
    )
    parser.add_argument("--write", action="store_true", help="Apply file updates. Without this flag, only preview.")
    parser.add_argument("--yes", action="store_true", help="Required with --write to confirm target writes")
    parser.add_argument("--project-root", default=".", help="Project root path")
    parser.add_argument("--tool", choices=["codex", "claude"], default="codex", help="User-level target home")
    parser.add_argument("--project-store", default=".pr-learning/store.v1.json", help="Project store path")
    parser.add_argument("--user-store", help="Optional custom user store path")
    return parser.parse_args()


def resolve_project_target(root: Path) -> Path:
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    if agents.exists():
        return agents
    if claude.exists():
        return claude
    return agents


def resolve_user_target(tool: str) -> Path:
    base = Path.home() / (".codex" if tool == "codex" else ".claude")
    agents = base / "AGENTS.md"
    claude = base / "CLAUDE.md"
    if agents.exists():
        return agents
    if claude.exists():
        return claude
    return agents


def resolve_user_store(tool: str, explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser()
    base = Path.home() / (".codex" if tool == "codex" else ".claude")
    return base / "pr-learning" / "store.v1.json"


def parse_selection(select_value: str, available_ids: set[str]) -> set[str]:
    if select_value == "none":
        return set()
    if select_value == "all":
        return set(available_ids)

    selected = {part.strip() for part in select_value.split(",") if part.strip()}
    unknown = selected - available_ids
    if unknown:
        raise ValueError(f"Unknown candidate IDs: {', '.join(sorted(unknown))}")
    return selected


def ensure_pr_learning_sections(content: str) -> str:
    if "## PR Learnings" not in content:
        if content and not content.endswith("\n"):
            content += "\n"
        content += "\n## PR Learnings\n\n### Rules\n\n### Learnings\n"

    section_match = re.search(r"## PR Learnings[\s\S]*?(?=\n## |\Z)", content)
    if not section_match:
        return content

    section = section_match.group(0)
    if "### Rules" not in section:
        section += "\n### Rules\n"
    if "### Learnings" not in section:
        section += "\n### Learnings\n"

    return content[: section_match.start()] + section + content[section_match.end() :]


def append_item(content: str, subsection: str, bullet_text: str, metadata_comment: str) -> str:
    content = ensure_pr_learning_sections(content)

    section_match = re.search(r"## PR Learnings[\s\S]*?(?=\n## |\Z)", content)
    if not section_match:
        return content

    section = section_match.group(0)
    sub_match = re.search(rf"### {subsection}[\s\S]*?(?=\n### |\Z)", section)

    if not sub_match:
        section += f"\n### {subsection}\n"
        sub_match = re.search(rf"### {subsection}[\s\S]*?(?=\n### |\Z)", section)
    if not sub_match:
        return content

    block = sub_match.group(0)
    insertion = f"\n- {bullet_text}\n  <!-- {metadata_comment} -->\n"
    new_block = block.rstrip() + insertion

    section = section[: sub_match.start()] + new_block + section[sub_match.end() :]
    return content[: section_match.start()] + section + content[section_match.end() :]


def load_store(path: Path, repo: str | None = None) -> dict[str, Any]:
    return read_json(
        path,
        default={
            "version": 1,
            "repo": repo,
            "seen_observation_keys": [],
            "codified": [],
        },
    )


def store_existing_signatures(store: dict[str, Any]) -> set[tuple[str, str]]:
    signatures: set[tuple[str, str]] = set()
    for record in store.get("codified", []):
        scope = record.get("scope") or ""
        semantic = (record.get("dedupe") or {}).get("semantic_key")
        if semantic and scope:
            signatures.add((scope, semantic))
    return signatures


def source_summary(candidate: dict[str, Any]) -> str:
    chunks: list[str] = []
    for ref in candidate.get("source_refs", []):
        pr_number = ref.get("pr_number")
        urls = ref.get("urls") or []
        first_url = urls[0] if urls else ""
        chunk = f"PR#{pr_number}:{first_url}" if first_url else f"PR#{pr_number}"
        chunks.append(chunk)
    return "|".join(chunks)


def metadata_comment(candidate: dict[str, Any], scope: str) -> str:
    return (
        f"pr-learning:v=1 type={candidate['type']} scope={scope} "
        f"key={candidate['dedupe']['semantic_key']} sim={candidate['dedupe']['fuzzy_key']} "
        f"sources={source_summary(candidate)} "
        f"confidence={candidate['confidence']['acceptance_average']}"
    )


def append_store_records(store: dict[str, Any], inserted: list[dict[str, Any]], target_path: Path, scope: str) -> None:
    signatures = store_existing_signatures(store)
    for candidate in inserted:
        signature = (scope, candidate["dedupe"]["semantic_key"])
        if signature in signatures:
            continue
        store.setdefault("codified", []).append(
            {
                "candidate_id": candidate["id"],
                "dedupe": candidate["dedupe"],
                "inserted_at": now_iso(),
                "sources": candidate["source_refs"],
                "text_fingerprint": f"sha256:{sha256_hex(candidate['proposed_text'])}",
                "scope": scope,
                "file_path": str(target_path),
            }
        )
        signatures.add(signature)


def main() -> None:
    args = parse_args()

    payload = read_json(Path(args.candidates), default={})
    candidates = payload.get("candidates", [])
    if not candidates:
        raise SystemExit("No candidates found. Run build_candidates.py first.")

    candidate_map = {candidate["id"]: candidate for candidate in candidates}
    selected_ids = parse_selection(args.select, set(candidate_map))
    selected = [candidate_map[candidate_id] for candidate_id in sorted(selected_ids)]

    project_selected = [c for c in selected if c.get("scope_suggestion") == "project"]
    user_selected = [c for c in selected if c.get("scope_suggestion") == "user"]

    project_target = resolve_project_target(Path(args.project_root).resolve())
    user_target = resolve_user_target(args.tool)
    user_store = resolve_user_store(args.tool, args.user_store)

    preview = {
        "total_candidates": len(candidates),
        "selected": [c["id"] for c in selected],
        "project_target": str(project_target),
        "user_target": str(user_target),
        "project_store": str(Path(args.project_store)),
        "user_store": str(user_store),
        "write": args.write,
    }
    print("Selection summary")
    print(json.dumps(preview, indent=2))

    if not args.write:
        return
    if not args.yes:
        raise SystemExit("Refusing to write without explicit confirmation. Re-run with --write --yes.")
    if not selected:
        raise SystemExit("Nothing selected. Refusing to write.")

    project_content = project_target.read_text() if project_target.exists() else ""
    user_content = user_target.read_text() if user_target.exists() else ""

    existing_project_keys = parse_pr_learning_keys(project_content)
    existing_user_keys = parse_pr_learning_keys(user_content)

    inserted_project: list[dict[str, Any]] = []
    inserted_user: list[dict[str, Any]] = []

    for candidate in project_selected:
        semantic_key = candidate["dedupe"]["semantic_key"]
        if semantic_key in existing_project_keys:
            continue

        subsection = "Rules" if candidate["type"] == "rule" else "Learnings"
        project_content = append_item(project_content, subsection, candidate["proposed_text"], metadata_comment(candidate, "project"))
        existing_project_keys.add(semantic_key)
        inserted_project.append(candidate)

    for candidate in user_selected:
        semantic_key = candidate["dedupe"]["semantic_key"]
        if semantic_key in existing_user_keys:
            continue

        subsection = "Rules" if candidate["type"] == "rule" else "Learnings"
        user_content = append_item(user_content, subsection, candidate["proposed_text"], metadata_comment(candidate, "user"))
        existing_user_keys.add(semantic_key)
        inserted_user.append(candidate)

    project_changed = bool(inserted_project)
    user_changed = bool(inserted_user)

    if project_changed:
        project_target.parent.mkdir(parents=True, exist_ok=True)
        project_target.write_text(project_content)
    if user_changed:
        user_target.parent.mkdir(parents=True, exist_ok=True)
        user_target.write_text(user_content)

    if not project_changed and not user_changed:
        print("No new insertions were required (all selected candidates already codified).")
        return

    project_store_path = Path(args.project_store)
    project_data = load_store(project_store_path, repo=payload.get("repo"))
    user_data = load_store(user_store, repo=None)

    append_store_records(project_data, inserted_project, project_target, "project")
    append_store_records(user_data, inserted_user, user_target, "user")

    write_json(project_store_path, project_data)
    write_json(user_store, user_data)

    written = [
        *[{"id": c["id"], "scope": "project", "target": str(project_target)} for c in inserted_project],
        *[{"id": c["id"], "scope": "user", "target": str(user_target)} for c in inserted_user],
    ]

    print("Write complete")
    print(
        json.dumps(
            {
                "written": written,
                "project_store": str(project_store_path),
                "user_store": str(user_store),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
