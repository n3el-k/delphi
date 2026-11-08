from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import create_db
from app.routers import learner, webhooks
from app.services.progress import NotSeededError


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_db()
    yield


app = FastAPI(title="Hack the Change 2026 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(NotSeededError)
async def not_seeded(_: Request, exc: NotSeededError) -> JSONResponse:
    # Only our own, known error gets a friendly message. Any other bug stays a plain 500
    # so internal details never reach the client.
    return JSONResponse(status_code=503, content={"detail": "The app has no data yet. Run the seed script."})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(learner.router)
app.include_router(webhooks.router)
