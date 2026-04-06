from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.routers import auto_review, patterns, review


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.include_router(patterns.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")
app.include_router(auto_review.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
