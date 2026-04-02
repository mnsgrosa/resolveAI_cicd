"""Generate an API key for a repository and seed it in the database.

Usage:
    python -m scripts.create_api_key owner/repo
"""

import asyncio
import hashlib
import secrets
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_db
from app.models.pattern import ApiKey


async def create_key(repository: str) -> str:
    await init_db()
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    async with AsyncSessionLocal() as session:
        api_key = ApiKey(
            id=str(uuid.uuid4()),
            key_hash=key_hash,
            repository=repository,
            is_active=True,
        )
        session.add(api_key)
        await session.commit()

    return raw_key


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.create_api_key owner/repo")
        sys.exit(1)

    repository = sys.argv[1]
    raw_key = asyncio.run(create_key(repository))
    print(f"API key created for '{repository}':")
    print(f"  {raw_key}")
    print(f"\nSave this key — it cannot be recovered.")


if __name__ == "__main__":
    main()
