#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

RESOLVE_THREAD_MUTATION = """
mutation ResolveThread($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""


def run(args: list[str]) -> str:
    result = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply PR comment reply/resolve actions.")
    parser.add_argument(
        "--input",
        default="-",
        help="Action file path. Use '-' (default) to read JSON from stdin.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute actions. Without this flag, print dry-run plan only.",
    )
    return parser.parse_args()


def read_actions(input_arg: str) -> list[dict[str, Any]]:
    if input_arg == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(input_arg).read_text()
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("Input JSON must be an array of action objects.")
    return payload


def require(action: dict[str, Any], keys: list[str]) -> None:
    missing = [key for key in keys if key not in action]
    if missing:
        raise ValueError(f"Missing required keys: {', '.join(missing)}")


def apply_action(action: dict[str, Any]) -> dict[str, Any]:
    action_type = action.get("action")
    if action_type == "reply_review_comment":
        require(action, ["repo", "pr_number", "comment_id", "body"])
        repo = action["repo"]
        pr_number = int(action["pr_number"])
        comment_id = int(action["comment_id"])
        body = str(action["body"])
        response = run(
            [
                "gh",
                "api",
                f"repos/{repo}/pulls/{pr_number}/comments/{comment_id}/replies",
                "-f",
                f"body={body}",
            ]
        )
        payload = json.loads(response)
        return {"action": action_type, "ok": True, "response": payload}

    if action_type == "create_issue_comment":
        require(action, ["repo", "pr_number", "body"])
        repo = action["repo"]
        pr_number = int(action["pr_number"])
        body = str(action["body"])
        response = run(
            [
                "gh",
                "api",
                f"repos/{repo}/issues/{pr_number}/comments",
                "-f",
                f"body={body}",
            ]
        )
        payload = json.loads(response)
        return {"action": action_type, "ok": True, "response": payload}

    if action_type == "resolve_thread":
        require(action, ["thread_id"])
        thread_id = str(action["thread_id"])
        response = run(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={RESOLVE_THREAD_MUTATION}",
                "-f",
                f"threadId={thread_id}",
            ]
        )
        payload = json.loads(response)
        if payload.get("errors"):
            raise RuntimeError(f"GraphQL errors: {payload['errors']}")
        is_resolved = (
            payload.get("data", {})
            .get("resolveReviewThread", {})
            .get("thread", {})
            .get("isResolved")
        )
        if is_resolved is not True:
            raise RuntimeError("Thread resolve mutation returned success=false.")
        return {"action": action_type, "ok": True, "response": payload}

    raise ValueError(f"Unsupported action type: {action_type}")


def main() -> int:
    args = parse_args()
    actions = read_actions(args.input)

    if not args.apply:
        print(json.dumps({"ok": True, "mode": "dry-run", "actions": actions}, indent=2))
        return 0

    results: list[dict[str, Any]] = []
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            results.append(
                {
                    "index": idx,
                    "action": None,
                    "ok": False,
                    "error": "Each action must be an object.",
                }
            )
            continue
        try:
            action_result = apply_action(action)
            action_result["index"] = idx
            results.append(action_result)
        except Exception as exc:
            results.append(
                {"index": idx, "action": action.get("action"), "ok": False, "error": str(exc)}
            )

    ok = all(result.get("ok") for result in results)
    print(json.dumps({"ok": ok, "results": results}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
