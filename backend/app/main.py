"""Main FastAPI entry point for Nobaj platform."""

import logging
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
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
LANG_DIR = STATIC_DIR / "lang"
SUPPORTED_LANGUAGES = ("ar", "en", "es", "fr", "de", "pt", "it", "tr", "ru", "zh", "ja", "ko", "hi")
OPEN_GRAPH_LOCALES = {
    "ar": "ar_SA", "en": "en_US", "es": "es_ES", "fr": "fr_FR",
    "de": "de_DE", "pt": "pt_BR", "it": "it_IT", "tr": "tr_TR",
    "ru": "ru_RU", "zh": "zh_CN", "ja": "ja_JP", "ko": "ko_KR", "hi": "hi_IN",
}
SEO_METADATA = {}
for language in SUPPORTED_LANGUAGES:
    with (LANG_DIR / f"{language}.json").open(encoding="utf-8") as language_file:
        language_data = json.load(language_file)
    SEO_METADATA[language] = {
        key: language_data[key]
        for key in ("page_title", "meta_description", "og_title", "og_description")
    }


def language_path(language: str) -> str:
    return "/" if language == "en" else f"/{language}"


def preferred_language(request: Request) -> str:
    """Choose a saved language, then the best supported browser language."""
    saved_language = request.cookies.get("nobaj_lang", "").lower()
    if saved_language in SUPPORTED_LANGUAGES:
        return saved_language

    accepted_languages = []
    for preference in request.headers.get("accept-language", "").split(","):
        parts = preference.strip().split(";", 1)
        language = parts[0].strip().replace("_", "-").split("-", 1)[0].lower()
        quality = 1.0
        if len(parts) == 2 and parts[1].strip().startswith("q="):
            try:
                quality = float(parts[1].strip()[2:])
            except ValueError:
                quality = 0.0
        if quality > 0 and language in SUPPORTED_LANGUAGES:
            accepted_languages.append((quality, len(accepted_languages), language))

    if accepted_languages:
        return max(accepted_languages, key=lambda item: (item[0], -item[1]))[2]
    return "en"


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
    """Serve English by default and route visitors to their preferred locale."""
    requested_language = request.query_params.get("lang", "").lower()
    language = requested_language if requested_language in SUPPORTED_LANGUAGES else preferred_language(request)
    if language != "en":
        response = RedirectResponse(language_path(language), status_code=302)
        response.headers["Vary"] = "Accept-Language, Cookie"
        response.headers["Cache-Control"] = "private, no-store"
        return response

    response = await render_index_page(request, "en")
    response.headers["Vary"] = "Accept-Language, Cookie"
    response.headers["Cache-Control"] = "private, no-store"
    return response


async def render_index_page(request: Request, language: str):
    visitor_id = request.cookies.get("nobaj_visitor_id")
    if not visitor_id:
        import uuid
        visitor_id = uuid.uuid4().hex
    analytics.record_visit(
        visitor_id=visitor_id,
        path=request.url.path,
        user_agent=request.headers.get("user-agent", ""),
    )
    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": settings.APP_NAME,
            "site_url": settings.PUBLIC_BASE_URL.rstrip("/"),
            "canonical_url": f"{settings.PUBLIC_BASE_URL.rstrip('/')}{language_path(language)}",
            "page_language": language,
            "seo_meta": SEO_METADATA[language],
            "open_graph_locale": OPEN_GRAPH_LOCALES[language],
            "language_alternates": [
                (code, f"{settings.PUBLIC_BASE_URL.rstrip('/')}{language_path(code)}")
                for code in SUPPORTED_LANGUAGES
            ],
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
            "max_duration_minutes": settings.MAX_DURATION_SECONDS // 60,
            "file_ttl_minutes": settings.FILE_TTL_MINUTES,
            "current_year": datetime.now().year,
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
    response.set_cookie(
        "nobaj_lang",
        language,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
    )
    response.headers["Content-Language"] = language
    return response


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt():
    """Publish crawl guidance and point search engines to the XML sitemap."""
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /health\n"
        "Disallow: /docs\n"
        "Disallow: /redoc\n"
        "Disallow: /openapi.json\n"
        f"Sitemap: {base_url}/sitemap.xml\n",
        media_type="text/plain",
    )


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    """Expose each canonical language landing page to search crawlers."""
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")
    urls = "".join(
        f"  <url><loc>{base_url}{language_path(language)}</loc></url>\n"
        for language in SUPPORTED_LANGUAGES
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}"
        "</urlset>\n"
    )
    return PlainTextResponse(content, media_type="application/xml")


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Render the protected dashboard shell; data is loaded with an admin token."""
    response = templates.TemplateResponse(
        request,
        "admin.html",
        {"app_name": settings.APP_NAME},
    )
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.get("/{language}", response_class=HTMLResponse, include_in_schema=False)
async def localized_index_page(request: Request, language: str):
    """Render a language-specific, crawlable landing page."""
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="Page not found")
    return await render_index_page(request, language)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
