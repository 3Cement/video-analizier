from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.routes import router
from app.api.auth_routes import router as auth_router
from app.api.library import router as library_router
from app.config import get_settings
from app.db import get_session, init_db
from app.models import Source
from app.share import render_share_page

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app() -> FastAPI:
    settings = get_settings()
    settings.ensure_dirs()
    init_db()

    app = FastAPI(
        title="video-analizier",
        description="Source-grounded analysis for YouTube, audio, PDF and text (NotebookLM-style).",
        version="0.3.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(library_router, prefix="/api/library")

    assets_dir = FRONTEND_DIR / "assets"
    if FRONTEND_DIR.exists() and assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(FRONTEND_DIR / "index.html")

        @app.get("/robots.txt")
        def robots() -> FileResponse:
            return FileResponse(FRONTEND_DIR / "robots.txt", media_type="text/plain")

        @app.get("/sitemap.xml")
        def sitemap() -> Response:
            base = (get_settings().public_base_url or "").rstrip("/")
            db = get_session()
            try:
                slugs = db.scalars(
                    select(Source.share_slug).where(
                        Source.is_public.is_(True),
                        Source.share_slug.is_not(None),
                        Source.status == "ready",
                    )
                ).all()
            finally:
                db.close()
            urls = ["/", *[f"/s/{slug}" for slug in slugs if slug]]
            body = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            ]
            for path in urls:
                loc = f"{base}{path}" if base else path
                body.append(f"  <url><loc>{loc}</loc><changefreq>weekly</changefreq></url>")
            body.append("</urlset>")
            return Response("\n".join(body), media_type="application/xml")

        @app.get("/s/{slug}")
        def share_page(slug: str) -> HTMLResponse:
            db = get_session()
            try:
                source = db.scalar(
                    select(Source)
                    .where(
                        Source.share_slug == slug,
                        Source.is_public.is_(True),
                        Source.status == "ready",
                    )
                    .options(selectinload(Source.summaries))
                )
                if source is None:
                    raise HTTPException(status_code=404, detail="Shared summary not found")
                latest = source.summaries[-1].content if source.summaries else ""
                html_doc = render_share_page(
                    title=source.title or "Podsumowanie",
                    summary_md=latest,
                    video_url=source.url,
                    slug=slug,
                    settings=get_settings(),
                    method=source.transcript_method,
                    duration_seconds=source.duration_seconds,
                )
                return HTMLResponse(html_doc)
            finally:
                db.close()

    
    @app.get("/manifest.webmanifest")
    def pwa_manifest():
        path = FRONTEND_DIR / "manifest.webmanifest"
        return FileResponse(path, media_type="application/manifest+json")

    @app.get("/sw.js")
    def service_worker():
        return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript")

    return app


app = create_app()
