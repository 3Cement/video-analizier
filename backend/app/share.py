from __future__ import annotations

import html
import re
import secrets
from pathlib import Path

from app.config import Settings

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def make_share_slug() -> str:
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12]


def plain_preview(markdown: str, limit: int = 160) -> str:
    text = re.sub(r"[#*_>`\[\]]+", " ", markdown or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def render_markdown_html(markdown: str) -> str:
    lines = (markdown or "").splitlines()
    out: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_list()
            continue
        if line.startswith("### "):
            close_list()
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            close_list()
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            close_list()
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(line[2:])}</li>")
        else:
            close_list()
            out.append(f"<p>{html.escape(line)}</p>")
    close_list()
    return "\n".join(out) or "<p class='muted'>Brak podsumowania.</p>"


def render_share_page(
    *,
    title: str,
    summary_md: str,
    video_url: str | None,
    slug: str,
    settings: Settings,
    method: str | None = None,
    duration_seconds: float | None = None,
) -> str:
    template = (FRONTEND_DIR / "share.html").read_text(encoding="utf-8")
    base = (settings.public_base_url or "").rstrip("/")
    canonical = f"{base}/s/{slug}" if base else f"/s/{slug}"
    description = plain_preview(summary_md)
    meta_bits = [method or "summary"]
    if duration_seconds:
        meta_bits.append(f"{int(duration_seconds // 60)} min")
    video_link = ""
    if video_url:
        safe = html.escape(video_url, quote=True)
        video_link = (
            f'<p><a class="ghost-link" href="{safe}" target="_blank" rel="noreferrer">'
            "Otwórz oryginalny film</a></p>"
        )
    return (
        template.replace("__TITLE__", html.escape(title or "Podsumowanie"))
        .replace("__DESCRIPTION__", html.escape(description))
        .replace("__CANONICAL__", html.escape(canonical, quote=True))
        .replace("__META__", html.escape(" · ".join(meta_bits)))
        .replace("__VIDEO_LINK__", video_link)
        .replace("__SUMMARY_HTML__", render_markdown_html(summary_md))
    )
