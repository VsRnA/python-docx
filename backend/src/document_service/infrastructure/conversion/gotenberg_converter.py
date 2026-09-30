from pathlib import PurePath

import httpx


class GotenbergDocumentPdfConverter:
    def __init__(self, base_url: str, *, timeout_seconds: float = 180.0) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/forms/libreoffice/convert"
        self._timeout = timeout_seconds

    async def convert_docx(self, *, filename: str, content: bytes) -> bytes:
        safe_filename = PurePath(filename).name or "source.docx"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._endpoint,
                files={
                    "files": (
                        safe_filename,
                        content,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        response.raise_for_status()
        if not response.content.startswith(b"%PDF-"):
            raise RuntimeError("DOCX converter returned a non-PDF response")
        return response.content
