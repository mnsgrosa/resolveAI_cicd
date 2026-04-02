from pydantic import BaseModel


class ReviewRequest(BaseModel):
    repository: str       # "owner/repo"
    pr_number: int
    diff_raw: str         # raw git diff text
    base_ref: str
    head_ref: str
    github_token: str     # passed per-request, never stored
    commit_sha: str


class ReviewResponse(BaseModel):
    status: str           # "success" | "error"
    review_id: str | None = None
    comments_count: int
    summary: str
