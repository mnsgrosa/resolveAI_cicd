import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_key import validate_api_key
from app.database import get_session
from app.models.pattern import Pattern
from app.schemas.diagnose import DiagnoseRequest, DiagnoseResponse
from app.services.anthropic_service import diagnose_code

logger = logging.getLogger(__name__)
router = APIRouter(tags=["diagnose"])


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    body: DiagnoseRequest,
    _: str = Depends(validate_api_key),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(Pattern).where(Pattern.repository == body.repository)
    )
    patterns = result.scalars().all()

    if patterns:
        patterns_content = "\n\n---\n\n".join(
            f"### {p.name}\n{p.content}" for p in patterns
        )
    else:
        patterns_content = None

    try:
        data = await diagnose_code(
            code=body.code,
            issue_description=body.issue_description,
            patterns=patterns_content,
            file_path=body.file_path,
        )
    except Exception as exc:
        logger.exception("Anthropic diagnosis failed")
        raise HTTPException(status_code=502, detail=f"AI diagnosis failed: {exc}") from exc

    return DiagnoseResponse(**data)
