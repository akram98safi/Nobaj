"""Main FastAPI entry point for Nobaj platform."""

import logging
import json
import hashlib
from functools import lru_cache
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
LANGUAGE_DATA = {}
for language in SUPPORTED_LANGUAGES:
    with (LANG_DIR / f"{language}.json").open(encoding="utf-8") as language_file:
        language_data = json.load(language_file)
    SEO_METADATA[language] = {
        key: language_data[key]
        for key in ("page_title", "meta_description", "og_title", "og_description")
    }
    LANGUAGE_DATA[language] = language_data

TOOL_PAGES = {
    "video-compressor": {
        "tab_key": "tab_compress",
        "description_key": "seo_tool_compress_description",
        "setting_keys": ("comp_level", "comp_res", "comp_codec"),
        "operation": "compress",
    },
    "audio-extractor": {
        "tab_key": "tab_audio",
        "description_key": "seo_tool_audio_description",
        "setting_keys": ("audio_format", "audio_bitrate", "audio_channels"),
        "operation": "audio",
    },
    "video-to-gif": {
        "tab_key": "tab_gif",
        "description_key": "seo_tool_gif_description",
        "setting_keys": ("gif_fps", "gif_res", "gif_trim"),
        "operation": "gif",
    },
}

LANGUAGE_NAMES = {
    "ar": "العربية", "en": "English", "es": "Español", "fr": "Français",
    "de": "Deutsch", "pt": "Português", "it": "Italiano", "tr": "Türkçe",
    "ru": "Русский", "zh": "简体中文", "ja": "日本語", "ko": "한국어", "hi": "हिन्दी",
}


@lru_cache(maxsize=1)
def static_asset_versions():
    assets = {
        "css": STATIC_DIR / "css" / "app.min.css",
        "app": STATIC_DIR / "js" / "app.js",
        "admin": STATIC_DIR / "js" / "admin.js",
    }
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        for name, path in assets.items()
        if path.is_file()
    }


@lru_cache(maxsize=1)
def language_asset_version():
    return hashlib.sha256(
        b"".join(path.read_bytes() for path in sorted(LANG_DIR.glob("*.json")))
    ).hexdigest()[:12]


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
        target = language_path(language)
        if request.url.query:
            target = f"{target}?{request.url.query}"
        response = RedirectResponse(target, status_code=302)
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
            "language_name": LANGUAGE_NAMES[language],
            "seo_meta": SEO_METADATA[language],
            "translations": LANGUAGE_DATA[language],
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
            "google_site_verification": settings.GOOGLE_SITE_VERIFICATION,
            "language_options": [(code, LANGUAGE_NAMES[code]) for code in SUPPORTED_LANGUAGES],
            "asset_versions": static_asset_versions(),
            "language_asset_version": language_asset_version(),
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
    """Expose canonical landing, tool, and trust pages to search crawlers."""
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")
    landing_urls = "".join(
        f"  <url><loc>{base_url}{language_path(language)}</loc></url>\n"
        for language in SUPPORTED_LANGUAGES
    )
    tool_urls = "".join(
        f"  <url><loc>{base_url}{language_path(language).rstrip('/')}/tools/{slug}</loc></url>\n"
        for language in SUPPORTED_LANGUAGES
        for slug in TOOL_PAGES
    )
    trust_urls = "".join(
        f"  <url><loc>{base_url}{path}</loc></url>\n"
        for path in ("/privacy", "/terms", "/contact", "/ar/privacy", "/ar/terms", "/ar/contact")
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{landing_urls}{tool_urls}{trust_urls}"
        "</urlset>\n"
    )
    return PlainTextResponse(content, media_type="application/xml")


def tool_page_context(request: Request, language: str, slug: str):
    tool = TOOL_PAGES[slug]
    translations = LANGUAGE_DATA[language]
    prefix = language_path(language).rstrip("/")
    canonical_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{prefix}/tools/{slug}"
    return {
        "language": language,
        "direction": "rtl" if language == "ar" else "ltr",
        "language_name": LANGUAGE_NAMES[language],
        "language_options": [
            (code, LANGUAGE_NAMES[code], f"{settings.PUBLIC_BASE_URL.rstrip('/')}{language_path(code).rstrip('/')}/tools/{slug}")
            for code in SUPPORTED_LANGUAGES
        ],
        "translations": translations,
        "tool": tool,
        "tool_name": translations[tool["tab_key"]],
        "description": translations[tool["description_key"]],
        "setting_names": [translations[key] for key in tool["setting_keys"]],
        "seo_title": f"{translations[tool['tab_key']]} | Nobaj",
        "canonical_url": canonical_url,
        "site_url": settings.PUBLIC_BASE_URL.rstrip("/"),
        "alternates": [
            (code, f"{settings.PUBLIC_BASE_URL.rstrip('/')}{language_path(code).rstrip('/')}/tools/{slug}")
            for code in SUPPORTED_LANGUAGES
        ],
        "language_path": language_path(language),
        "open_graph_locale": OPEN_GRAPH_LOCALES[language],
        "google_site_verification": settings.GOOGLE_SITE_VERIFICATION,
        "file_ttl_minutes": settings.FILE_TTL_MINUTES,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "max_duration_minutes": settings.MAX_DURATION_SECONDS // 60,
        "asset_versions": static_asset_versions(),
        "language_asset_version": language_asset_version(),
        "current_year": datetime.now().year,
    }


async def render_tool_page(request: Request, language: str, slug: str):
    if slug not in TOOL_PAGES:
        raise HTTPException(status_code=404, detail="Page not found")
    context = tool_page_context(request, language, slug)
    response = templates.TemplateResponse(request, "tool.html", context)
    response.headers["Content-Language"] = language
    return response


@app.get("/tools/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def default_tool_page(request: Request, slug: str):
    """Serve English tool pages by default and respect saved/browser language."""
    if slug not in TOOL_PAGES:
        raise HTTPException(status_code=404, detail="Page not found")
    language = preferred_language(request)
    if language == "en":
        response = await render_tool_page(request, "en", slug)
        response.headers["Vary"] = "Accept-Language, Cookie"
        response.headers["Cache-Control"] = "private, no-store"
        return response
    prefix = language_path(language).rstrip("/")
    response = RedirectResponse(f"{prefix}/tools/{slug}", status_code=302)
    response.headers["Vary"] = "Accept-Language, Cookie"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.get("/{language}/tools/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def localized_tool_page(request: Request, language: str, slug: str):
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="Page not found")
    return await render_tool_page(request, language, slug)


TRUST_COPY = {
    "en": {
        "privacy": ("Privacy policy", "How Nobaj handles your media and basic usage data.", [
            ("Media files", "Files you upload are sent to the Nobaj server for the conversion you request. Temporary uploads and generated outputs are automatically removed after {ttl} minutes. Do not upload files you are not authorized to process."),
            ("Basic analytics", "Nobaj uses a random visitor identifier cookie to estimate unique visits. When the landing page is opened, the service records its path and a shortened browser user-agent for first-party analytics. It does not store raw IP addresses. Analytics records are kept in the service database; no fixed deletion schedule is currently configured."),
            ("Cookies and external services", "A preference cookie remembers your language. Google AdSense may be loaded when configured. Third-party providers may receive standard connection data when your browser requests their resources."),
            ("Questions", "For support, use the Nobaj project issue tracker linked on the Contact page. Do not include private media or sensitive information in a public report."),
        ]),
        "terms": ("Terms of use", "Rules for using Nobaj media tools.", [
            ("Use of the service", "Nobaj provides media conversion tools as available. You are responsible for having the rights and permissions needed to upload and process each file."),
            ("Limits and availability", "Upload size, media duration, queue capacity, and supported formats are limited by the values shown by the service. Processing may fail or be temporarily unavailable; keep your original files."),
            ("Your files", "You retain responsibility for the files you submit and the results you download. Temporary inputs and outputs are automatically removed after {ttl} minutes. Do not use the service to violate others’ rights or applicable law."),
            ("Changes", "Nobaj may change or discontinue features to maintain the service. Use of the site means you agree to these terms and the Privacy Policy."),
        ]),
        "contact": ("Contact Nobaj", "Get help or report a problem with the service.", [
            ("Project support", "Nobaj does not have a public support email at this time. For questions and bug reports, open an issue in the project repository. Please do not post personal data or private media files."),
        ]),
    },
    "ar": {
        "privacy": ("سياسة الخصوصية", "كيف يتعامل نُباج مع ملفاتك وبيانات الاستخدام الأساسية.", [
            ("ملفات الوسائط", "تُرفع الملفات إلى خادم نُباج لتنفيذ التحويل الذي تطلبه. تُحذف الملفات المؤقتة والنتائج تلقائيًا بعد {ttl} دقيقة. لا ترفع ملفات لا تملك صلاحية معالجتها."),
            ("إحصاءات الاستخدام", "يستخدم نُباج ملف ارتباط بمعرّف عشوائي لتقدير عدد الزوار الفريدين. يسجّل مسار الصفحة وبيانات مختصرة عن متصفحك لأغراض إحصائية داخلية، ولا يخزّن عنوان IP الخام. تُحفظ سجلات الإحصاءات في قاعدة بيانات الخدمة، ولا توجد حاليًا مدة حذف محددة لها."),
            ("ملفات الارتباط والخدمات الخارجية", "يحفظ ملف ارتباط تفضيل اللغة. وقد يحمّل الموقع إعلانات Google AdSense عند تفعيلها. قد تستقبل الجهات الخارجية بيانات الاتصال المعتادة عند طلب المتصفح لمواردها."),
            ("الاستفسارات", "للدعم، استخدم صفحة المشكلات في مستودع مشروع نُباج والمشار إليه في صفحة التواصل. لا تضع ملفات خاصة أو معلومات حساسة في بلاغ عام."),
        ]),
        "terms": ("شروط الاستخدام", "القواعد المنظمة لاستخدام أدوات نُباج لمعالجة الوسائط.", [
            ("استخدام الخدمة", "يوفر نُباج أدوات تحويل الوسائط حسب التوفر. أنت مسؤول عن امتلاك الحقوق والأذونات اللازمة لرفع كل ملف ومعالجته."),
            ("الحدود والتوفر", "تخضع الخدمة لحدود حجم الرفع ومدة الوسائط وسعة الانتظار والصيغ المدعومة الموضحة في الموقع. قد تتعطل المعالجة أو تتوقف الخدمة مؤقتًا؛ احتفظ بنسخك الأصلية."),
            ("ملفاتك", "تبقى مسؤولًا عن الملفات التي ترسلها والنتائج التي تنزّلها. تُحذف الملفات المؤقتة والنتائج تلقائيًا بعد {ttl} دقيقة. لا تستخدم الخدمة لانتهاك حقوق الآخرين أو القوانين المعمول بها."),
            ("التغييرات", "قد يغيّر نُباج ميزات الخدمة أو يوقفها للمحافظة عليها. استخدام الموقع يعني موافقتك على هذه الشروط وسياسة الخصوصية."),
        ]),
        "contact": ("تواصل مع نُباج", "اطلب المساعدة أو أبلغ عن مشكلة في الخدمة.", [
            ("دعم المشروع", "لا يوجد لدى نُباج بريد دعم عام حاليًا. للأسئلة وبلاغات الأخطاء، افتح بلاغًا في مستودع المشروع. يُرجى عدم نشر معلومات شخصية أو ملفات وسائط خاصة."),
        ]),
    },
}


def trust_context(language: str, page: str):
    content_language = language if language in TRUST_COPY else "en"
    title, description, sections = TRUST_COPY[content_language][page]
    prefix = "/ar" if content_language == "ar" else ""
    return {
        "language": content_language,
        "direction": "rtl" if content_language == "ar" else "ltr",
        "page": page,
        "title": title,
        "description": description,
        "sections": sections,
        "file_ttl_minutes": settings.FILE_TTL_MINUTES,
        "canonical_url": f"{settings.PUBLIC_BASE_URL.rstrip('/')}{prefix}/{page}",
        "site_url": settings.PUBLIC_BASE_URL.rstrip("/"),
        "language_path": prefix or "/",
        "current_year": datetime.now().year,
        "asset_versions": static_asset_versions(),
        "alternates": [
            (code, f"{settings.PUBLIC_BASE_URL.rstrip('/')}{'/ar' if code == 'ar' else ''}/{page}")
            for code in ("en", "ar")
        ],
        "default_url": f"{settings.PUBLIC_BASE_URL.rstrip('/')}/{page}",
    }


async def trust_page(request: Request, page: str):
    if page not in {"privacy", "terms", "contact"}:
        raise HTTPException(status_code=404, detail="Page not found")
    # Legal content is currently maintained in English and Arabic only.
    language = preferred_language(request)
    if language == "ar":
        response = RedirectResponse(f"/ar/{page}", status_code=302)
        response.headers["Vary"] = "Accept-Language, Cookie"
        response.headers["Cache-Control"] = "private, no-store"
        return response
    context = trust_context("en", page)
    response = templates.TemplateResponse(request, "info.html", context)
    response.headers["Content-Language"] = "en"
    response.headers["Vary"] = "Accept-Language, Cookie"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_page(request: Request):
    return await trust_page(request, "privacy")


@app.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms_page(request: Request):
    return await trust_page(request, "terms")


@app.get("/contact", response_class=HTMLResponse, include_in_schema=False)
async def contact_page(request: Request):
    return await trust_page(request, "contact")


@app.get("/ar/{page}", response_class=HTMLResponse, include_in_schema=False)
async def arabic_trust_page(request: Request, page: str):
    if page not in {"privacy", "terms", "contact"}:
        raise HTTPException(status_code=404, detail="Page not found")
    response = templates.TemplateResponse(request, "info.html", trust_context("ar", page))
    response.headers["Content-Language"] = "ar"
    return response


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Render the protected dashboard shell; data is loaded with an admin token."""
    response = templates.TemplateResponse(
        request,
        "admin.html",
        {
            "app_name": settings.APP_NAME,
            "asset_versions": static_asset_versions(),
            "language_asset_version": language_asset_version(),
        },
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
