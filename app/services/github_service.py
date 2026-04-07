import base64
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


def _parse_diff_line_ranges(diff_raw: str) -> dict[str, set[int]]:
    """Parse diff hunk headers and return {file_path: set_of_valid_new_file_lines}."""
    import re as _re
    result: dict[str, set[int]] = {}
    current_file: str | None = None
    hunk_re = _re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    for line in diff_raw.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            if current_file not in result:
                result[current_file] = set()
        elif current_file and line.startswith("@@"):
            m = hunk_re.match(line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                for ln in range(start, start + count):
                    result[current_file].add(ln)

    return result


async def post_review(
    repository: str,
    pr_number: int,
    commit_sha: str,
    plan: ReviewPlan,
    github_token: str,
    diff_raw: str = "",
) -> str | None:
    """Post a PR review with inline comments. Returns the GitHub review ID."""
    owner, repo = repository.split("/", 1)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    valid_lines = _parse_diff_line_ranges(diff_raw) if diff_raw else {}

    review_comments = []
    for issue in plan.issues:
        if not issue.file:
            continue
        # Skip comments whose line falls outside the diff hunks to avoid GitHub 422
        if valid_lines:
            allowed = valid_lines.get(issue.file, set())
            if issue.line_end not in allowed:
                logger.warning(
                    "Skipping comment on %s line %d — not in diff hunk (valid: %s)",
                    issue.file,
                    issue.line_end,
                    sorted(allowed)[:10],
                )
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


def parse_diff_files(diff_raw: str) -> list[dict]:
    """Extract new files from a unified diff. Returns list of {"path": str, "content": str}."""
    files = []
    current_file: str | None = None
    current_lines: list[str] = []
    is_new_file = False

    for line in diff_raw.splitlines():
        if line.startswith("diff --git "):
            if current_file and is_new_file:
                files.append({"path": current_file, "content": "\n".join(current_lines)})
            current_file = None
            current_lines = []
            is_new_file = False
        elif line.startswith("new file mode"):
            is_new_file = True
        elif line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("+") and not line.startswith("+++") and current_file and is_new_file:
            current_lines.append(line[1:])

    if current_file and is_new_file:
        files.append({"path": current_file, "content": "\n".join(current_lines)})

    return files


def _split_diff_by_file(diff_raw: str) -> list[tuple[str, str]]:
    """Split a unified diff into (filename, file_diff_chunk) pairs."""
    files: list[tuple[str, str]] = []
    current_lines: list[str] = []
    current_name: str | None = None

    for line in diff_raw.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current_name is not None:
                files.append((current_name, "".join(current_lines)))
            current_lines = [line]
            # Fallback name from diff --git a/... b/... header
            parts = line.split(" b/", 1)
            current_name = parts[1].strip() if len(parts) == 2 else line.strip()
        else:
            if line.startswith("+++ b/"):
                current_name = line[6:].strip()
            if current_lines is not None:
                current_lines.append(line)

    if current_name is not None and current_lines:
        files.append((current_name, "".join(current_lines)))

    return files


MAX_COMMENT_LENGTH = 65_536


async def post_diff_comment(
    repository: str,
    pr_number: int,
    diff_raw: str,
    github_token: str,
) -> str | None:
    """Post the git diff as a collapsible comment in the PR conversation tab."""
    owner, repo = repository.split("/", 1)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    file_diffs = _split_diff_by_file(diff_raw)
    total_files = len(file_diffs)

    header = "## Code Changes\n\n"
    body = header
    included = 0

    for filename, chunk in file_diffs:
        section = (
            f"<details>\n"
            f"<summary><code>{filename}</code></summary>\n\n"
            f"```diff\n{chunk}```\n\n"
            f"</details>\n\n"
        )

        # If this single file alone exceeds remaining budget, truncate its content
        remaining = MAX_COMMENT_LENGTH - len(body) - 200  # reserve for truncation notice
        if len(section) > remaining:
            if included == 0:
                # Must include at least one file — truncate its content
                truncated_chunk = chunk[:remaining - 60] + "\n... (truncated)\n"
                section = (
                    f"<details>\n"
                    f"<summary><code>{filename}</code></summary>\n\n"
                    f"```diff\n{truncated_chunk}```\n\n"
                    f"</details>\n\n"
                )
                body += section
                included += 1
            break

        body += section
        included += 1

    if included < total_files:
        omitted = total_files - included
        body += f"> **Note:** Diff truncated — {omitted} file(s) omitted due to GitHub comment size limit ({total_files} files total).\n"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={"body": body}, headers=headers)
        if resp.status_code not in (200, 201):
            logger.error(
                "GitHub API error %s posting diff comment: %s", resp.status_code, resp.text
            )
            resp.raise_for_status()
        return str(resp.json().get("id"))


async def get_branch_sha(repository: str, branch: str, github_token: str) -> str:
    """Return the commit SHA at the tip of a branch."""
    owner, repo = repository.split("/", 1)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.error("GitHub API error %s getting branch SHA: %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return str(resp.json()["object"]["sha"])


async def create_branch(repository: str, branch_name: str, from_sha: str, github_token: str) -> None:
    """Create a new branch on the remote from the given commit SHA."""
    owner, repo = repository.split("/", 1)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/refs"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": f"refs/heads/{branch_name}", "sha": from_sha}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 422 and "already exists" in resp.text:
            logger.info("Branch %s already exists, continuing", branch_name)
            return
        if resp.status_code not in (200, 201):
            logger.error("GitHub API error %s creating branch: %s", resp.status_code, resp.text)
            resp.raise_for_status()


async def create_pull_request(
    repository: str,
    title: str,
    body: str,
    head: str,
    base: str,
    github_token: str,
) -> dict:
    """Create a new PR. Returns dict with 'number', 'html_url', 'id'."""
    owner, repo = repository.split("/", 1)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code not in (200, 201):
            logger.error(
                "GitHub API error %s creating PR: %s", resp.status_code, resp.text
            )
            resp.raise_for_status()
        data = resp.json()
        return {
            "number": data["number"],
            "html_url": data["html_url"],
            "id": str(data.get("id", "")),
        }


async def create_or_update_file(
    repository: str,
    file_path: str,
    content: str,
    message: str,
    branch: str,
    github_token: str,
    sha: str | None = None,
) -> str:
    """Create or update a file in a branch. Returns the new file SHA."""
    owner, repo = repository.split("/", 1)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}"

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    encoded_content = base64.b64encode(content.encode()).decode()

    # If SHA not provided, try to get existing file's SHA
    if sha is None:
        async with httpx.AsyncClient(timeout=30) as client:
            head_resp = await client.get(url, params={"ref": branch}, headers=headers)
            if head_resp.status_code == 200:
                sha = head_resp.json().get("sha")

    payload: dict = {
        "message": message,
        "content": encoded_content,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    async with httpx.AsyncClient(timeout=30) as client:
        if sha:
            resp = await client.put(url, json=payload, headers=headers)
        else:
            resp = await client.put(url, json=payload, headers=headers)
        if resp.status_code not in (200, 201):
            logger.error(
                "GitHub API error %s creating file: %s", resp.status_code, resp.text
            )
            resp.raise_for_status()
        return str(resp.json()["content"]["sha"])
