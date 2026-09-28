import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import engine
from app.db.schema_patches import ensure_schema
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.subscriptions import router as subscription_router
from app.routes.newsletters import router as newsletter_router


ensure_schema(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None

    if settings.scheduler_enabled:
        from app.scheduler import scheduler_loop

        scheduler = asyncio.create_task(scheduler_loop())

    yield

    if scheduler is not None:
        scheduler.cancel()

        with suppress(asyncio.CancelledError):
            await scheduler


app = FastAPI(
    title="AINow API",
    description="Backend API for AINow AI Newsletter",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted({
        "http://localhost:5173",
        settings.frontend_url.rstrip("/"),
    }),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(subscription_router)
app.include_router(newsletter_router)
app.include_router(admin_router)

@app.get("/")
def root():
    return {
        "message": "AINow API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }