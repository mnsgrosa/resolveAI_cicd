"""Send a real PR diff to the local ResolveAI API for end-to-end testing.

Usage:
    python -m scripts.test_local_review owner/repo <pr_number> --api-key <key>

Requires:
    - Local API running at http://localhost:8000 (uvicorn app.main:app --reload)
    - gh CLI authenticated (gh auth login)
"""

import argparse
import subprocess
import sys

import httpx


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running {' '.join(cmd)}:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Test local ResolveAI review against a real PR")
    parser.add_argument("repository", help="Repository in owner/repo format")
    parser.add_argument("pr_number", type=int, help="Pull request number")
    parser.add_argument("--api-key", required=True, help="ResolveAI API key")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL (default: http://localhost:8000)")
    args = parser.parse_args()

    print(f"Fetching diff for {args.repository}#{args.pr_number}...")
    diff = _run(["gh", "pr", "diff", str(args.pr_number), "--repo", args.repository])
    if not diff:
        print("Diff is empty — nothing to review.", file=sys.stderr)
        sys.exit(1)

    commit_sha = _run([
        "gh", "pr", "view", str(args.pr_number),
        "--repo", args.repository,
        "--json", "headRefOid",
        "--jq", ".headRefOid",
    ])

    base_ref = _run([
        "gh", "pr", "view", str(args.pr_number),
        "--repo", args.repository,
        "--json", "baseRefName",
        "--jq", ".baseRefName",
    ])

    head_ref = _run([
        "gh", "pr", "view", str(args.pr_number),
        "--repo", args.repository,
        "--json", "headRefName",
        "--jq", ".headRefName",
    ])

    github_token = _run(["gh", "auth", "token"])

    payload = {
        "repository": args.repository,
        "pr_number": args.pr_number,
        "diff_raw": diff,
        "commit_sha": commit_sha,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "github_token": github_token,
    }

    print(f"Diff: {len(diff)} chars across {diff.count('diff --git')} file(s)")
    print(f"Commit: {commit_sha[:12]}  {base_ref} ← {head_ref}")
    print(f"Posting to {args.api_url}/api/v1/review ...")

    response = httpx.post(
        f"{args.api_url}/api/v1/review",
        json=payload,
        headers={"X-API-Key": args.api_key},
        timeout=120.0,
    )

    print(f"\nStatus: {response.status_code}")
    try:
        data = response.json()
        print(f"Review ID:      {data.get('review_id')}")
        print(f"Comments:       {data.get('comments_count')}")
        print(f"Summary:        {data.get('summary')}")
    except Exception:
        print(response.text)

    if response.status_code not in (200, 201):
        sys.exit(1)


if __name__ == "__main__":
    main()
