import httpx


class HttpPdfRenderer:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def render(
        self,
        *,
        html: str,
        title: str,
        theme_id: str,
        theme_version: str,
    ) -> bytes:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{self._base_url}/render/pdf",
                json={
                    "html": html,
                    "title": title,
                    "themeId": theme_id,
                    "themeVersion": theme_version,
                },
            )
            response.raise_for_status()
            return response.content

    async def bundle_html(
        self,
        *,
        html: str,
        title: str,
        theme_id: str,
        theme_version: str,
    ) -> bytes:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{self._base_url}/render/html",
                json={
                    "html": html,
                    "title": title,
                    "themeId": theme_id,
                    "themeVersion": theme_version,
                },
            )
            response.raise_for_status()
            return response.content
