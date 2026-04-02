import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_key import validate_api_key
from app.database import get_session
from app.models.pattern import Pattern
from app.schemas.review import ReviewRequest, ReviewResponse
from app.services.anthropic_service import generate_fixes, plan_review
from app.services.github_service import post_review

logger = logging.getLogger(__name__)
router = APIRouter(tags=["review"])


@router.post("/review", response_model=ReviewResponse)
async def review(
    body: ReviewRequest,
    _: str = Depends(validate_api_key),
    db: AsyncSession = Depends(get_session),
):
    # Load pattern for this repository (optional)
    result = await db.execute(
        select(Pattern).where(
            Pattern.repository == body.repository, Pattern.name == "default"
        )
    )
    pattern = result.scalar_one_or_none()
    patterns_content = pattern.content if pattern else None

    # Phase 1: planning
    try:
        plan = await plan_review(body.diff_raw, patterns_content)
    except Exception as exc:
        logger.exception("Anthropic planning failed")
        raise HTTPException(status_code=502, detail=f"AI planning failed: {exc}") from exc

    # Phase 2: generate fixes for issues that need them
    try:
        plan = await generate_fixes(plan, body.diff_raw)
    except Exception as exc:
        logger.exception("Anthropic fix generation failed")
        raise HTTPException(status_code=502, detail=f"AI fix generation failed: {exc}") from exc

    # Post review to GitHub
    review_id = None
    try:
        review_id = await post_review(
            repository=body.repository,
            pr_number=body.pr_number,
            commit_sha=body.commit_sha,
            plan=plan,
            github_token=body.github_token,
        )
    except Exception as exc:
        logger.exception("GitHub review posting failed")
        raise HTTPException(status_code=502, detail=f"GitHub posting failed: {exc}") from exc

    return ReviewResponse(
        status="success",
        review_id=review_id,
        comments_count=len(plan.issues),
        summary=plan.summary,
    )
