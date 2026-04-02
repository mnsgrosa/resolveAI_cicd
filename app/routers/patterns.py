from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_key import validate_api_key
from app.database import get_session
from app.models.pattern import Pattern
from app.schemas.pattern import PatternResponse, PatternUpdate

router = APIRouter(tags=["patterns"])


@router.get("/patterns/{owner}/{repo}", response_model=PatternResponse)
async def get_pattern(
    owner: str,
    repo: str,
    _: str = Depends(validate_api_key),
    db: AsyncSession = Depends(get_session),
):
    repository = f"{owner}/{repo}"
    result = await db.execute(
        select(Pattern).where(Pattern.repository == repository, Pattern.name == "default")
    )
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return pattern


@router.put("/patterns/{owner}/{repo}", response_model=PatternResponse)
async def upsert_pattern(
    owner: str,
    repo: str,
    body: PatternUpdate,
    _: str = Depends(validate_api_key),
    db: AsyncSession = Depends(get_session),
):
    repository = f"{owner}/{repo}"
    result = await db.execute(
        select(Pattern).where(Pattern.repository == repository, Pattern.name == "default")
    )
    pattern = result.scalar_one_or_none()

    if pattern:
        pattern.content = body.content
    else:
        pattern = Pattern(repository=repository, name="default", content=body.content)
        db.add(pattern)

    await db.commit()
    await db.refresh(pattern)
    return pattern


@router.delete("/patterns/{owner}/{repo}", status_code=204)
async def delete_pattern(
    owner: str,
    repo: str,
    _: str = Depends(validate_api_key),
    db: AsyncSession = Depends(get_session),
):
    repository = f"{owner}/{repo}"
    result = await db.execute(
        select(Pattern).where(Pattern.repository == repository, Pattern.name == "default")
    )
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    await db.delete(pattern)
    await db.commit()
