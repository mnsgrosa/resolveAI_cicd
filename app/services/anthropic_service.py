import asyncio
import json
import logging

import anthropic

from app.config import settings
from app.services.prompts import DIAGNOSE_SYSTEM_PROMPT, EXECUTOR_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ReviewIssue:
    def __init__(self, data: dict):
        self.file: str = data.get("file", "")
        self.line_start: int = data.get("line_start", 1)
        self.line_end: int = data.get("line_end", 1)
        self.severity: str = data.get("severity", "suggestion")
        self.description: str = data.get("description", "")
        self.needs_fix: bool = data.get("needs_fix", False)
        self.suggestion: str | None = None
        self.explanation: str | None = None


class ReviewPlan:
    def __init__(self, data: dict):
        self.summary: str = data.get("summary", "")
        self.issues: list[ReviewIssue] = [ReviewIssue(i) for i in data.get("issues", [])]


async def plan_review(diff: str, patterns: str | None) -> ReviewPlan:
    """Phase 1: analyze diff and produce a structured review plan."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    patterns_section = patterns or "No patterns defined. Use general best practices."
    user_content = (
        f"## Repository Patterns\n{patterns_section}\n\n"
        f"## Diff\n```diff\n{diff}\n```"
    )

    response = await client.messages.create(
        model=settings.planner_model,
        max_tokens=4096,
        system=PLANNER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()
    data = json.loads(raw)
    return ReviewPlan(data)


async def _generate_single_fix(issue: ReviewIssue, diff: str) -> ReviewIssue:
    """Generate a concrete code fix for a single issue."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_content = (
        f"## Issue\nFile: {issue.file} (lines {issue.line_start}-{issue.line_end})\n"
        f"Severity: {issue.severity}\n"
        f"Description: {issue.description}\n\n"
        f"## Relevant Diff\n```diff\n{diff}\n```"
    )

    try:
        response = await client.messages.create(
            model=settings.executor_model,
            max_tokens=2048,
            system=EXECUTOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text.strip()
        data = json.loads(raw)
        issue.suggestion = data.get("suggestion")
        issue.explanation = data.get("explanation")
    except Exception:
        logger.exception("Failed to generate fix for issue in %s", issue.file)

    return issue


_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".jsx": "javascript", ".go": "go",
    ".rs": "rust", ".java": "java", ".rb": "ruby",
    ".c": "c", ".cpp": "cpp", ".cs": "csharp", ".php": "php",
}


def _infer_language(file_path: str) -> str:
    ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
    return _EXT_TO_LANGUAGE.get(ext, "")


async def diagnose_code(
    code: str,
    issue_description: str,
    patterns: str | None,
    file_path: str,
) -> dict:
    """Analyze code against patterns and diagnose the described issue."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    patterns_section = patterns or "No patterns defined. Use general best practices."

    language = _infer_language(file_path)
    lang_hint = f" ({language})" if language else ""

    user_content = (
        f"## Repository Patterns\n{patterns_section}\n\n"
        f"## Code\nFile: {file_path}{lang_hint}\n```{language}\n{code}\n```\n\n"
        f"## Issue Description\n{issue_description}"
    )

    response = await client.messages.create(
        model=settings.planner_model,
        max_tokens=4096,
        system=DIAGNOSE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()
    return json.loads(raw)


async def generate_fixes(plan: ReviewPlan, diff: str) -> ReviewPlan:
    """Phase 2: generate concrete code suggestions for issues that need fixes."""
    fix_issues = [i for i in plan.issues if i.needs_fix]
    if fix_issues:
        await asyncio.gather(*[_generate_single_fix(i, diff) for i in fix_issues])
    return plan
