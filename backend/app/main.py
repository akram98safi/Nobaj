"""Main FastAPI entry point for Nobaj platform."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.app.core.config import settings
from backend.app.routes.api import router as api_router
from backend.app.routes.health import router as health_router
from backend.app.services.cleanup.cleaner import cleaner
from backend.app.services.analytics import analytics
from backend.app.services.queue.queue_manager import queue_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nobaj")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATES_DIR = FRONTEND_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown procedures."""
    logger.info("Starting Nobaj media processing engine...")
    settings.ensure_directories()
    analytics.db_path = settings.ANALYTICS_DB_PATH
    analytics.initialize()

    # Start queue background workers
    await queue_manager.start()

    # Start auto-cleanup background task
    await cleaner.start()

    yield

    logger.info("Shutting down Nobaj engine...")
    await queue_manager.stop()
    await cleaner.stop()


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add baseline browser protections to every app response."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include API endpoints
app.include_router(health_router)
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Render main interactive user interface."""
    visitor_id = request.cookies.get("nobaj_visitor_id")
    if not visitor_id:
        import uuid
        visitor_id = uuid.uuid4().hex
    analytics.record_visit(
        visitor_id=visitor_id,
        path="/",
        user_agent=request.headers.get("user-agent", ""),
    )
    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": settings.APP_NAME,
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
            "max_duration_minutes": settings.MAX_DURATION_SECONDS // 60,
            "file_ttl_minutes": settings.FILE_TTL_MINUTES,
            "adsense_client": settings.GOOGLE_ADSENSE_CLIENT,
            "adsense_slot_top": settings.GOOGLE_ADSENSE_SLOT_TOP,
            "adsense_slot_bottom": settings.GOOGLE_ADSENSE_SLOT_BOTTOM,
        },
    )
    response.set_cookie(
        "nobaj_visitor_id",
        visitor_id,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
    )
    return response


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Render the protected dashboard shell; data is loaded with an admin token."""
    return templates.TemplateResponse(
        request,
        "admin.html",
        {"app_name": settings.APP_NAME},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
