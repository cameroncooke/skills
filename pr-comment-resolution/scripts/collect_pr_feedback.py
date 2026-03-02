#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

THREADS_QUERY = """
query PullRequestThreads(
  $owner: String!
  $name: String!
  $number: Int!
  $after: String
) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      number
      url
      title
      state
      baseRefName
      headRefName
      reviewThreads(first: 50, after: $after) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          comments(first: 100) {
            nodes {
              id
              databaseId
              url
              body
              createdAt
              updatedAt
              diffHunk
              path
              line
              originalLine
              startLine
              originalStartLine
              author { login }
              replyTo { databaseId }
              commit { oid }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

THREAD_COMMENTS_QUERY = """
query ThreadComments($threadId: ID!, $after: String) {
  node(id: $threadId) {
    ... on PullRequestReviewThread {
      comments(first: 100, after: $after) {
        nodes {
          id
          databaseId
          url
          body
          createdAt
          updatedAt
          diffHunk
          path
          line
          originalLine
          startLine
          originalStartLine
          author { login }
          replyTo { databaseId }
          commit { oid }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""


def run(args: list[str], *, stdin_text: str | None = None) -> str:
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
    return result.stdout.strip()


def run_json(args: list[str], *, stdin_text: str | None = None) -> Any:
    raw = run(args, stdin_text=stdin_text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON output: {exc}\nOutput: {raw[:500]}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect all PR review feedback for comment auditing.")
    parser.add_argument("--repo", help="owner/repo. Defaults to current repository.")
    parser.add_argument("--pr", help="PR number or full PR URL. Optional when auto-detect succeeds.")
    parser.add_argument(
        "--branch",
        help="Branch name to match against PR head. Defaults to current local branch.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.add_argument(
        "--view",
        choices=["full", "counts", "bodies", "thread-locations"],
        default="full",
        help="Response view. Use one view at a time.",
    )
    parser.add_argument(
        "--include-resolved-threads",
        action="store_true",
        help="Include resolved review threads. Default excludes them.",
    )
    parser.add_argument(
        "--exclude-outdated-threads",
        action="store_true",
        help="Exclude outdated review threads.",
    )
    parser.add_argument(
        "--exclude-bot-comments",
        action="store_true",
        help="Exclude bot-authored issue comments/reviews/thread comments.",
    )
    parser.add_argument(
        "--include-review-summaries",
        action="store_true",
        help="Include review summary bodies from pull request reviews. Default excludes them.",
    )
    return parser.parse_args()


def parse_pr_number(value: str) -> int:
    value = value.strip()
    if value.isdigit():
        return int(value)
    match = re.search(r"/pull/(\d+)", value)
    if match:
        return int(match.group(1))
    raise ValueError(f"Could not parse PR number from: {value}")


def split_repo(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError(f"Expected owner/repo, got {repo}")
    return tuple(repo.split("/", 1))  # type: ignore[return-value]


def fetch_pr_summary_rest(repo: str, pr_number: int) -> dict[str, Any]:
    owner, name = split_repo(repo)
    payload = run_json(["gh", "api", f"repos/{owner}/{name}/pulls/{pr_number}"])
    return {
        "number": payload.get("number"),
        "url": payload.get("html_url"),
        "title": payload.get("title"),
        "state": str(payload.get("state", "")).upper(),
        "isDraft": payload.get("draft"),
        "baseRefName": (payload.get("base") or {}).get("ref"),
        "headRefName": (payload.get("head") or {}).get("ref"),
        "author": {
            "login": ((payload.get("user") or {}).get("login")),
            "name": None,
            "is_bot": (((payload.get("user") or {}).get("type")) == "Bot"),
        },
    }


def resolve_repo(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo
    return run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])


def resolve_current_branch(explicit_branch: str | None) -> str:
    if explicit_branch:
        return explicit_branch
    return run(["git", "branch", "--show-current"]).strip()


def resolve_actor_login() -> str:
    return run(["gh", "api", "user", "-q", ".login"]).strip()


def detect_pr(
    repo: str, explicit_pr: str | None, branch: str, actor_login: str
) -> tuple[int | None, dict[str, Any]]:
    if explicit_pr:
        pr_number = parse_pr_number(explicit_pr)
        pr = fetch_pr_summary_rest(repo, pr_number)
        return pr_number, {"method": "explicit", "candidates": [pr]}

    pr_view_error: str | None = None
    if branch:
        try:
            current = run_json(
                [
                    "gh",
                    "pr",
                    "view",
                    branch,
                    "--repo",
                    repo,
                    "--json",
                    "number,url,title,state,headRefName,baseRefName",
                ]
            )
            return int(current["number"]), {"method": "gh-pr-view", "candidates": [current]}
        except Exception as exc:
            pr_view_error = str(exc)

    if not branch:
        return None, {
            "method": "no-local-branch",
            "candidates": [],
            "reason": "Current git branch is empty (detached HEAD or unknown state).",
        }

    def list_candidates(head_selector: str) -> list[dict[str, Any]]:
        return run_json(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repo,
                "--head",
                head_selector,
                "--state",
                "all",
                "--limit",
                "10",
                "--json",
                "number,url,title,state,headRefName,baseRefName",
            ]
        )

    candidates = list_candidates(branch)
    if not candidates and actor_login:
        candidates = list_candidates(f"{actor_login}:{branch}")
    if len(candidates) == 1:
        return int(candidates[0]["number"]), {
            "method": "branch-match",
            "candidates": candidates,
            "gh_pr_view_error": pr_view_error,
        }
    if not candidates:
        return None, {
            "method": "branch-match",
            "candidates": [],
            "gh_pr_view_error": pr_view_error,
            "action_hint": "Provide --pr <number|url>.",
        }
    return None, {
        "method": "ambiguous-branch-match",
        "candidates": candidates,
        "gh_pr_view_error": pr_view_error,
        "action_hint": "Multiple PRs matched branch head. Provide --pr <number|url>.",
    }


def paginate_rest(path: str) -> list[dict[str, Any]]:
    page = 1
    out: list[dict[str, Any]] = []
    while True:
        batch = run_json(["gh", "api", f"{path}?per_page=100&page={page}"])
        if not isinstance(batch, list):
            raise RuntimeError(f"Expected list response for {path}, got {type(batch)}")
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out


def fetch_threads(owner: str, name: str, pr_number: int) -> list[dict[str, Any]]:
    after: str | None = None
    threads: list[dict[str, Any]] = []
    while True:
        payload = run_json(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={THREADS_QUERY}",
                "-f",
                f"owner={owner}",
                "-f",
                f"name={name}",
                "-F",
                f"number={pr_number}",
                *([] if after is None else ["-f", f"after={after}"]),
            ]
        )
        if "errors" in payload:
            raise RuntimeError(f"GraphQL errors: {payload['errors']}")
        node = payload["data"]["repository"]["pullRequest"]["reviewThreads"]
        threads.extend(node["nodes"])
        if not node["pageInfo"]["hasNextPage"]:
            break
        after = node["pageInfo"]["endCursor"]

    for thread in threads:
        comments = thread.get("comments", {})
        page_info = comments.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            continue
        thread_id = thread["id"]
        combined = comments.get("nodes", [])
        comment_after = page_info.get("endCursor")
        while comment_after:
            comment_payload = run_json(
                [
                    "gh",
                    "api",
                    "graphql",
                    "-f",
                    f"query={THREAD_COMMENTS_QUERY}",
                    "-f",
                    f"threadId={thread_id}",
                    "-f",
                    f"after={comment_after}",
                ]
            )
            if "errors" in comment_payload:
                raise RuntimeError(f"GraphQL errors: {comment_payload['errors']}")
            comment_node = comment_payload["data"]["node"]["comments"]
            combined.extend(comment_node["nodes"])
            if not comment_node["pageInfo"]["hasNextPage"]:
                break
            comment_after = comment_node["pageInfo"]["endCursor"]
        thread["comments"]["nodes"] = combined
        thread["comments"]["pageInfo"] = {"hasNextPage": False, "endCursor": None}
    return threads


def build_payload(repo: str, pr_number: int, branch: str, detection: dict[str, Any]) -> dict[str, Any]:
    owner, name = split_repo(repo)
    issue_comments = paginate_rest(f"repos/{owner}/{name}/issues/{pr_number}/comments")
    reviews = paginate_rest(f"repos/{owner}/{name}/pulls/{pr_number}/reviews")
    threads = fetch_threads(owner, name, pr_number)
    pr = fetch_pr_summary_rest(repo, pr_number)
    return {
        "repo": repo,
        "branch": branch,
        "pr": pr,
        "detection": detection,
        "issue_comments": issue_comments,
        "reviews": reviews,
        "review_threads": threads,
        "counts": {
            "issue_comments": len(issue_comments),
            "reviews": len(reviews),
            "review_threads": len(threads),
            "inline_comments": sum(
                len(thread.get("comments", {}).get("nodes", [])) for thread in threads
            ),
        },
    }


def is_bot_author(user: dict[str, Any] | None) -> bool:
    if not user:
        return False
    login = str(user.get("login") or "").lower()
    user_type = str(user.get("type") or "").lower()
    return user_type == "bot" or login.endswith("[bot]") or login == "cursor"


def normalize_pr(pr: dict[str, Any]) -> dict[str, Any]:
    author = pr.get("author") or {}
    if not author and pr.get("user"):
        user = pr.get("user") or {}
        author = {
            "login": user.get("login"),
            "name": user.get("name"),
            "is_bot": str(user.get("type", "")).lower() == "bot",
        }
    return {
        "number": pr.get("number"),
        "url": pr.get("url") or pr.get("html_url"),
        "title": pr.get("title"),
        "state": pr.get("state"),
        "isDraft": pr.get("isDraft") if "isDraft" in pr else pr.get("draft"),
        "baseRefName": pr.get("baseRefName") or (pr.get("base") or {}).get("ref"),
        "headRefName": pr.get("headRefName") or (pr.get("head") or {}).get("ref"),
        "author": {
            "login": author.get("login"),
            "name": author.get("name"),
            "is_bot": bool(author.get("is_bot")),
        },
    }


def normalize_issue_comment(comment: dict[str, Any]) -> dict[str, Any]:
    user = comment.get("user") or {}
    return {
        "id": comment.get("id"),
        "url": comment.get("html_url") or comment.get("url"),
        "author": user.get("login"),
        "authorType": user.get("type"),
        "body": comment.get("body"),
        "createdAt": comment.get("created_at"),
        "updatedAt": comment.get("updated_at"),
    }


def normalize_review(review: dict[str, Any]) -> dict[str, Any]:
    user = review.get("user") or {}
    return {
        "id": review.get("id"),
        "url": review.get("html_url"),
        "state": review.get("state"),
        "author": user.get("login"),
        "authorType": user.get("type"),
        "body": review.get("body"),
        "submittedAt": review.get("submitted_at"),
        "commitId": review.get("commit_id"),
    }


def normalize_thread_comment(comment: dict[str, Any]) -> dict[str, Any]:
    author = comment.get("author") or {}
    reply_to = comment.get("replyTo") or {}
    commit = comment.get("commit") or {}
    return {
        "id": comment.get("id"),
        "databaseId": comment.get("databaseId"),
        "url": comment.get("url"),
        "author": author.get("login"),
        "body": comment.get("body"),
        "createdAt": comment.get("createdAt"),
        "updatedAt": comment.get("updatedAt"),
        "replyToDatabaseId": reply_to.get("databaseId"),
        "commitOid": commit.get("oid"),
    }


def transform_payload(data: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    issue_comments_raw = data.get("issue_comments", [])
    reviews_raw = data.get("reviews", [])
    threads_raw = data.get("review_threads", [])

    issue_comments: list[dict[str, Any]] = []
    for comment in issue_comments_raw:
        if args.exclude_bot_comments and is_bot_author(comment.get("user")):
            continue
        issue_comments.append(normalize_issue_comment(comment))

    reviews: list[dict[str, Any]] = []
    if args.include_review_summaries:
        for review in reviews_raw:
            if args.exclude_bot_comments and is_bot_author(review.get("user")):
                continue
            # Keep only reviews with textual content that an agent can audit.
            state = str(review.get("state") or "")
            body = str(review.get("body") or "").strip()
            if state not in {"COMMENTED", "CHANGES_REQUESTED"}:
                continue
            if not body:
                continue
            reviews.append(normalize_review(review))

    review_threads: list[dict[str, Any]] = []
    inline_count = 0
    for thread in threads_raw:
        is_resolved = bool(thread.get("isResolved"))
        is_outdated = bool(thread.get("isOutdated"))
        if not args.include_resolved_threads and is_resolved:
            continue
        if args.exclude_outdated_threads and is_outdated:
            continue

        comments = thread.get("comments", {}).get("nodes", [])
        normalized_comments: list[dict[str, Any]] = []
        for comment in comments:
            if args.exclude_bot_comments:
                author = (comment.get("author") or {}).get("login", "")
                if str(author).lower().endswith("[bot]") or str(author).lower() == "cursor":
                    continue
            normalized_comments.append(normalize_thread_comment(comment))

        if not normalized_comments:
            continue

        inline_count += len(normalized_comments)
        review_threads.append(
            {
                "id": thread.get("id"),
                "isResolved": is_resolved,
                "isOutdated": is_outdated,
                "path": thread.get("path"),
                "line": thread.get("line"),
                "originalLine": thread.get("originalLine"),
                "comments": normalized_comments,
            }
        )

    return {
        "branch": data.get("branch"),
        "pr": normalize_pr(data.get("pr", {})),
        "issue_comments": issue_comments,
        "reviews": reviews,
        "review_threads": review_threads,
    }


def derive_counts(response: dict[str, Any]) -> dict[str, int]:
    threads = response.get("review_threads", [])
    return {
        "issue_comments": len(response.get("issue_comments", [])),
        "reviews": len(response.get("reviews", [])),
        "review_threads": len(threads),
        "inline_comments": sum(len(thread.get("comments", [])) for thread in threads),
    }


def apply_view(response: dict[str, Any], view: str) -> dict[str, Any]:
    if view == "full":
        return response

    base = {
        "ok": response.get("ok"),
        "repo": response.get("repo"),
        "branch": response.get("branch"),
        "number": response.get("number"),
        "title": response.get("title"),
        "state": response.get("state"),
    }

    if view == "counts":
        return {**base, "counts": derive_counts(response)}

    if view == "bodies":
        return {
            **base,
            "issue_comment_bodies": [c.get("body") for c in response.get("issue_comments", [])],
            "review_bodies": [r.get("body") for r in response.get("reviews", [])],
            "inline_bodies": [
                c.get("body")
                for t in response.get("review_threads", [])
                for c in t.get("comments", [])
            ],
        }

    # thread-locations
    return {
        **base,
        "thread_locations": [
            {
                "id": t.get("id"),
                "isOutdated": t.get("isOutdated"),
                "path": t.get("path"),
                "line": t.get("line"),
                "originalLine": t.get("originalLine"),
                "firstAuthor": (t.get("comments", [{}])[0]).get("author")
                if t.get("comments")
                else None,
            }
            for t in response.get("review_threads", [])
        ],
    }


def main() -> int:
    args = parse_args()
    try:
        run(["gh", "auth", "status"])
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"GitHub CLI is not authenticated: {exc}",
                    "action": "run `gh auth login` and retry",
                },
                indent=2,
            )
        )
        return 1

    try:
        repo = resolve_repo(args.repo)
        branch = resolve_current_branch(args.branch)
        actor_login = resolve_actor_login()
        pr_number, detection = detect_pr(repo, args.pr, branch, actor_login)

        if pr_number is None:
            payload = {
                "ok": False,
                "repo": repo,
                "branch": branch,
                "detection": detection,
                "action": "Provide --pr <number|url> and rerun.",
            }
            print(json.dumps(payload, indent=2))
            return 2

        raw_data = build_payload(repo, pr_number, branch, detection)
        data = transform_payload(raw_data, args)
        pr = data.get("pr", {})
        response = {
            "ok": True,
            "repo": repo,
            "branch": data.get("branch"),
            "number": pr.get("number"),
            "title": pr.get("title"),
            "state": pr.get("state"),
            "baseRefName": pr.get("baseRefName"),
            "headRefName": pr.get("headRefName"),
            "issue_comments": data.get("issue_comments", []),
            "reviews": data.get("reviews", []),
            "review_threads": data.get("review_threads", []),
        }
        response = apply_view(response, args.view)
        if args.pretty:
            print(json.dumps(response, indent=2))
        else:
            print(json.dumps(response))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "action": "Verify repository/PR inputs and gh permissions, then retry.",
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
