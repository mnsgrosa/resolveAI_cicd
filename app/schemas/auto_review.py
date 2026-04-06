from pydantic import BaseModel


class AutoReviewRequest(BaseModel):
    repository: str  # "owner/repo"
    pr_number: int | None = None  # optional — if None and create_pr=True, a PR will be created
    diff_raw: str  # raw git diff text
    base_ref: str  # target branch (e.g. "main")
    head_ref: str  # source branch (e.g. "feature-branch")
    github_token: str  # passed per-request, never stored
    commit_sha: str
    create_pr: bool = False  # if True and no PR exists, create one
    pr_title: str = "ResolveAI Auto-Review"
    pr_body: str = "This PR was automatically created by ResolveAI for code review."


class AutoReviewResponse(BaseModel):
    status: str  # "success" | "error"
    review_id: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    comments_count: int
    summary: str
    report_file_path: str | None = None  # path to the .md report in the PR, if created
