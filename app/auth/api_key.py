import hashlib

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.pattern import ApiKey

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def validate_api_key(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_session),
) -> str:
    """Validate the API key and return the associated repository scope."""
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)  # noqa: E712
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return record.repository
