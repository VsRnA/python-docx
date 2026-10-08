from typing import Protocol


class PdfRenderer(Protocol):
    async def render(
        self,
        *,
        html: str,
        title: str,
        theme_id: str,
        theme_version: str,
        style_settings: dict | None = None,
    ) -> bytes: ...

    async def bundle_html(
        self,
        *,
        html: str,
        title: str,
        theme_id: str,
        theme_version: str,
        style_settings: dict | None = None,
    ) -> bytes: ...
