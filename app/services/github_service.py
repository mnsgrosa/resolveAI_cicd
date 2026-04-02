import logging

import httpx

from app.services.anthropic_service import ReviewIssue, ReviewPlan

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _format_comment(issue: ReviewIssue) -> str:
    severity_label = {"critical": "🔴 Critical", "warning": "🟡 Warning", "suggestion": "💡 Suggestion"}.get(
        issue.severity, issue.severity.capitalize()
    )
    lines = [f"**{severity_label}**: {issue.description}"]
    if issue.suggestion:
        lines.append(f"\n**Suggested fix:**\n```\n{issue.suggestion}\n```")
        if issue.explanation:
            lines.append(f"\n_{issue.explanation}_")
    return "\n".join(lines)


async def post_review(
    repository: str,
    pr_number: int,
    commit_sha: str,
    plan: ReviewPlan,
    github_token: str,
) -> str | None:
    """Post a PR review with inline comments. Returns the GitHub review ID."""
    owner, repo = repository.split("/", 1)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    review_comments = []
    for issue in plan.issues:
        if not issue.file:
            continue
        review_comments.append({
            "path": issue.file,
            "line": issue.line_end,
            "side": "RIGHT",
            "body": _format_comment(issue),
        })

    body = {
        "commit_id": commit_sha,
        "body": f"## ResolveAI Review\n\n{plan.summary}",
        "event": "COMMENT",
        "comments": review_comments,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=body, headers=headers)
        if resp.status_code not in (200, 201):
            logger.error(
                "GitHub API error %s posting review: %s", resp.status_code, resp.text
            )
            resp.raise_for_status()
        return str(resp.json().get("id"))
