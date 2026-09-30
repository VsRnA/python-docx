from __future__ import annotations

import hashlib
import html
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from weasyprint import HTML, default_url_fetcher


ROOT = Path(__file__).resolve().parent
THEMES_ROOT = ROOT / "themes"
SUPPORTED_THEMES = {"villartec-manual-a4@1.0", "villartec-manual-a5@1.0"}

app = FastAPI(title="Document PDF Renderer")


class RenderRequest(BaseModel):
    html: str = Field(min_length=1)
    themeId: str
    themeVersion: str
    title: str = ""


def _theme_css(payload: RenderRequest) -> str:
    key = f"{payload.themeId}@{payload.themeVersion}"
    if key not in SUPPORTED_THEMES:
        raise HTTPException(status_code=422, detail="Unsupported document theme")
    return (THEMES_ROOT / payload.themeId / payload.themeVersion / "print.css").read_text(
        encoding="utf-8"
    )


def _build_document(payload: RenderRequest) -> str:
    css = _theme_css(payload)
    return (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(payload.title)}</title><style>{css}</style>"
        f"</head><body>{payload.html}</body></html>"
    )


def _local_only_fetcher(url: str, *args, **kwargs):
    scheme = urlparse(url).scheme
    if scheme != "data":
        raise ValueError(f"External resource loading is disabled: {scheme or 'relative URL'}")
    return default_url_fetcher(url, *args, **kwargs)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "weasyprint"}


@app.post("/render/html")
def render_html(payload: RenderRequest) -> Response:
    document = _build_document(payload)
    return Response(content=document.encode("utf-8"), media_type="text/html")


@app.post("/render/pdf")
def render_pdf(payload: RenderRequest) -> Response:
    document = _build_document(payload)
    try:
        pdf = HTML(string=document, base_url=str(ROOT), url_fetcher=_local_only_fetcher).write_pdf()
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"PDF rendering failed: {error}") from error
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"X-Content-SHA256": hashlib.sha256(pdf).hexdigest()},
    )
