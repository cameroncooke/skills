#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common import now_iso, run_command, run_gh_graphql, run_gh_json, write_json

PR_DETAILS_QUERY = """
query PullRequestDetails($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      number
      title
      url
      state
      mergedAt
      updatedAt
      baseRefName
      headRefName
      author { login }
      comments(first: 100) {
        nodes {
          id
          url
          body
          createdAt
          author { login }
        }
        pageInfo { hasNextPage endCursor }
      }
      reviews(first: 100) {
        nodes {
          id
          url
          body
          state
          submittedAt
          author { login }
        }
        pageInfo { hasNextPage endCursor }
      }
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          resolvedBy { login }
          comments(first: 100) {
            nodes {
              id
              url
              body
              createdAt
              author { login }
              replyTo { id }
            }
            pageInfo { hasNextPage endCursor }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
      commits(first: 100) {
        nodes {
          commit {
            oid
            committedDate
            messageHeadline
            url
          }
        }
        pageInfo { hasNextPage endCursor }
      }
      files(first: 100) {
        nodes { path }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


def resolve_repo(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo
    return run_command(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()


def split_repo(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError(f"Expected owner/repo but got: {repo}")
    owner, name = repo.split("/", 1)
    return owner, name


def resolve_actor_login() -> str:
    return run_command(["gh", "api", "user", "-q", ".login"]).strip()


def build_search_query(login: str, since_days: int) -> str:
    parts = [f"is:pr involves:{login}", "sort:updated-desc"]
    if since_days > 0:
        since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).date().isoformat()
        parts.insert(1, f"updated:>={since_date}")
    return " ".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect PR feedback artifacts for pr-learning skill.")
    parser.add_argument("--repo", help="owner/repo. Defaults to current repository.")
    parser.add_argument(
        "--since-days",
        type=int,
        default=0,
        help="How many days back to search PRs. Use 0 to disable date filtering (default).",
    )
    parser.add_argument("--limit", type=int, default=200, help="Max PRs to fetch.")
    parser.add_argument("--out", default=".pr-learning/raw/feedback.json", help="Output JSON file path.")
    parser.add_argument(
        "--allow-truncated",
        action="store_true",
        help="Allow partial results when GraphQL pagination indicates more data exists.",
    )
    return parser.parse_args()


def fetch_file_patches(owner: str, name: str, pr_number: int) -> dict[str, str]:
    patches: dict[str, str] = {}
    page = 1
    while page <= 20:
        files_page = run_gh_json(["api", f"repos/{owner}/{name}/pulls/{pr_number}/files?per_page=100&page={page}"])
        if not files_page:
            break
        for file_entry in files_page:
            filename = file_entry.get("filename")
            patch = file_entry.get("patch")
            if filename and patch:
                patches[filename] = patch
        if len(files_page) < 100:
            break
        page += 1
    return patches


def main() -> None:
    args = parse_args()
    repo = resolve_repo(args.repo)
    owner, name = split_repo(repo)
    actor_login = resolve_actor_login()
    query = build_search_query(actor_login, args.since_days)

    prs = run_gh_json(
        [
            "pr",
            "list",
            "-R",
            repo,
            "--state",
            "all",
            "--search",
            query,
            "--limit",
            str(args.limit),
            "--json",
            "number,url,title,state,mergedAt,updatedAt,author,baseRefName,headRefName",
        ]
    )

    bundles = []
    for pr in prs:
        payload = run_gh_graphql(
            PR_DETAILS_QUERY,
            {"owner": owner, "name": name, "number": int(pr["number"])},
        )
        node = payload["data"]["repository"]["pullRequest"]
        file_patches = fetch_file_patches(owner, name, int(pr["number"]))
        bundles.append(
            {
                "pr": {
                    "number": node["number"],
                    "url": node["url"],
                    "title": node["title"],
                    "state": node["state"],
                    "mergedAt": node["mergedAt"],
                    "updatedAt": node["updatedAt"],
                    "baseRefName": node["baseRefName"],
                    "headRefName": node["headRefName"],
                    "author": (node.get("author") or {}).get("login"),
                },
                "issue_comments": node["comments"]["nodes"],
                "reviews": node["reviews"]["nodes"],
                "review_threads": node["reviewThreads"]["nodes"],
                "commits": [n["commit"] for n in node["commits"]["nodes"]],
                "files": [n["path"] for n in node["files"]["nodes"]],
                "file_patches": file_patches,
                "page_info": {
                    "comments_has_next": node["comments"]["pageInfo"]["hasNextPage"],
                    "reviews_has_next": node["reviews"]["pageInfo"]["hasNextPage"],
                    "threads_has_next": node["reviewThreads"]["pageInfo"]["hasNextPage"],
                    "thread_comments_has_next": any(
                        t.get("comments", {}).get("pageInfo", {}).get("hasNextPage")
                        for t in node["reviewThreads"]["nodes"]
                    ),
                    "commits_has_next": node["commits"]["pageInfo"]["hasNextPage"],
                    "files_has_next": node["files"]["pageInfo"]["hasNextPage"],
                },
            }
        )

    truncation_hits = []
    for bundle in bundles:
        for key, value in bundle.get("page_info", {}).items():
            if value:
                truncation_hits.append({"pr_number": bundle["pr"]["number"], "signal": key})

    if truncation_hits and not args.allow_truncated:
        first = truncation_hits[0]
        raise SystemExit(
            "Collection is truncated (GraphQL page limit reached). "
            f"First hit: PR #{first['pr_number']} ({first['signal']}). "
            "Re-run with --allow-truncated to proceed with partial data."
        )

    output = {
        "version": 1,
        "generated_at": now_iso(),
        "repo": repo,
        "query": query,
        "params": {
            "since_days": args.since_days,
            "limit": args.limit,
            "allow_truncated": args.allow_truncated,
        },
        "stats": {
            "pr_count": len(bundles),
            "thread_count": sum(len(bundle["review_threads"]) for bundle in bundles),
            "issue_comment_count": sum(len(bundle["issue_comments"]) for bundle in bundles),
            "truncation_hits": len(truncation_hits),
        },
        "truncated": bool(truncation_hits),
        "truncation_details": truncation_hits,
        "prs": bundles,
    }

    out_path = Path(args.out)
    write_json(out_path, output)
    print(f"Wrote feedback bundle: {out_path} ({len(bundles)} PRs)")
    if truncation_hits:
        print(f"Warning: output is truncated ({len(truncation_hits)} pagination signals).")


if __name__ == "__main__":
    main()
