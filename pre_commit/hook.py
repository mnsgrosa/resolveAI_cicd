"""ResolveAI pre-commit hook.

Runs linters on staged changes and writes a report to .resolveai/review.md.
Does not block commits — informational only for MVP.

Supported languages and their linters:
  - Python:     ruff
  - JavaScript/TypeScript: eslint
  - Go:         golangci-lint
  - Rust:       cargo clippy (via clippy-driver)
  - Java:       checkstyle
  - Ruby:       rubocop
  - C/C++:      cppcheck

Each linter runs only if the binary is available on PATH and matching files are staged.

Install via pre-commit framework (.pre-commit-config.yaml):

  repos:
    - repo: https://github.com/YOUR_ORG/resolveai-cicd
      rev: main
      hooks:
        - id: resolveai-review
"""

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c_cpp",
    ".cpp": "c_cpp",
    ".cc": "c_cpp",
    ".h": "c_cpp",
    ".hpp": "c_cpp",
}


def get_staged_diff() -> str:
    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=3"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def get_staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def group_files_by_language(files: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for f in files:
        ext = Path(f).suffix.lower()
        lang = EXTENSION_MAP.get(ext)
        if lang:
            groups.setdefault(lang, []).append(f)
    return groups


def _run_cmd(cmd: list[str]) -> list[str]:
    """Run a command and return stdout lines. Returns [] if the binary is missing."""
    if not shutil.which(cmd[0]):
        return []
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        return result.stdout.strip().splitlines()
    return []


def lint_python(files: list[str]) -> list[str]:
    return _run_cmd(["ruff", "check", "--output-format=text", *files])


def lint_javascript(files: list[str]) -> list[str]:
    return _run_cmd(["eslint", "--no-error-on-unmatched-pattern", "--format=unix", *files])


def lint_typescript(files: list[str]) -> list[str]:
    return _run_cmd(["eslint", "--no-error-on-unmatched-pattern", "--format=unix", *files])


def lint_go(files: list[str]) -> list[str]:
    return _run_cmd(["golangci-lint", "run", "--out-format=line-number", *files])


def lint_rust(files: list[str]) -> list[str]:
    # clippy operates on the whole crate, so we just trigger it if rust files are staged
    return _run_cmd(["cargo", "clippy", "--message-format=short", "--", "-D", "warnings"])


def lint_java(files: list[str]) -> list[str]:
    return _run_cmd(["checkstyle", "-c", "/google_checks.xml", *files])


def lint_ruby(files: list[str]) -> list[str]:
    return _run_cmd(["rubocop", "--format=emacs", *files])


def lint_c_cpp(files: list[str]) -> list[str]:
    return _run_cmd(["cppcheck", "--enable=warning,style", "--template=gcc", *files])


LINTERS: dict[str, callable] = {
    "python": lint_python,
    "javascript": lint_javascript,
    "typescript": lint_typescript,
    "go": lint_go,
    "rust": lint_rust,
    "java": lint_java,
    "ruby": lint_ruby,
    "c_cpp": lint_c_cpp,
}


def write_report(results: dict[str, list[str]]) -> Path:
    report_dir = Path(".resolveai")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "review.md"

    total = sum(len(v) for v in results.values())
    lines = [
        "# ResolveAI Pre-Commit Report",
        f"_Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
    ]

    if total == 0:
        lines.append("## No linting issues found.")
    else:
        lines.append(f"## Linting Issues ({total} found)\n")
        for lang, issues in sorted(results.items()):
            if issues:
                lines.append(f"### {lang.replace('_', '/').title()} ({len(issues)})\n")
                for issue in issues:
                    lines.append(f"- {issue}")
                lines.append("")

    report_path.write_text("\n".join(lines))
    return report_path


def main() -> int:
    diff = get_staged_diff()
    if not diff.strip():
        return 0

    staged = get_staged_files()
    groups = group_files_by_language(staged)

    results: dict[str, list[str]] = {}
    for lang, files in groups.items():
        linter = LINTERS.get(lang)
        if linter:
            issues = linter(files)
            if issues:
                results[lang] = issues

    report_path = write_report(results)
    total = sum(len(v) for v in results.values())

    if total:
        langs = ", ".join(sorted(results.keys()))
        print(f"ResolveAI: {total} issue(s) in [{langs}]. See {report_path}")
    else:
        print("ResolveAI: No issues found.")

    return 0  # Never block commits for MVP


if __name__ == "__main__":
    sys.exit(main())
