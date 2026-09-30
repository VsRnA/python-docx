from typing import Protocol


class DocumentPdfConverter(Protocol):
    async def convert_docx(self, *, filename: str, content: bytes) -> bytes: ...
