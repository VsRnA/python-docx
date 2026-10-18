import base64
import re
from io import BytesIO
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from document_service.application.ports.document_processor import ProcessedAsset


class DocxAssetExtractor:
    """Extract ordered, meaningful media without coupling the AI adapter to DOCX details."""

    def extract(self, document_id: str, content: bytes) -> list[ProcessedAsset]:
        try:
            with ZipFile(BytesIO(content)) as archive:
                media_names = [
                    name for name in archive.namelist() if name.startswith("word/media/") and not name.endswith("/")
                ]
                assets: list[ProcessedAsset] = []
                for name, source_pages in self._ordered_media_with_pages(archive, media_names):
                    image = archive.read(name)
                    mime_type = self._image_mime_type(name, image)
                    if mime_type is None or (len(image) < 2_048 and mime_type != "image/svg+xml"):
                        continue
                    filename = Path(name).name
                    assets.append(
                        ProcessedAsset(
                            external_id=str(uuid5(NAMESPACE_URL, f"{document_id}|{name}")),
                            filename=filename,
                            mime_type=mime_type,
                            base64_data=base64.b64encode(image).decode("ascii"),
                            alt=f"Изображение из исходного документа: {filename}",
                            source_pages=tuple(source_pages),
                        )
                    )
                return assets
        except (BadZipFile, KeyError, ElementTree.ParseError):
            return []

    @staticmethod
    def _ordered_media_with_pages(archive: ZipFile, media_names: list[str]) -> list[tuple[str, list[int]]]:
        rels_name = "word/_rels/document.xml.rels"
        document_name = "word/document.xml"
        if rels_name not in archive.namelist() or document_name not in archive.namelist():
            return [(name, []) for name in sorted(media_names)]

        relationships = ElementTree.fromstring(archive.read(rels_name))
        rel_targets = {relation.attrib.get("Id", ""): relation.attrib.get("Target", "") for relation in relationships}
        document = ElementTree.fromstring(archive.read(document_name))
        relationship_attribute = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
        ordered: list[str] = []
        pages_by_name: dict[str, list[int]] = {}
        page_number = 1
        for element in document.iter():
            local_name = element.tag.rsplit("}", 1)[-1]
            if local_name == "lastRenderedPageBreak":
                page_number += 1
                continue
            relation_id = element.attrib.get(relationship_attribute)
            target = rel_targets.get(relation_id or "", "")
            if not target:
                continue
            normalized = f"word/{target.lstrip('/')}" if not target.startswith("word/") else target
            normalized = normalized.replace("word/../", "")
            if normalized in media_names:
                if normalized not in ordered:
                    ordered.append(normalized)
                pages = pages_by_name.setdefault(normalized, [])
                if page_number not in pages:
                    pages.append(page_number)
        ordered.extend(name for name in sorted(media_names) if name not in ordered)
        return [(name, pages_by_name.get(name, [])) for name in ordered]

    @staticmethod
    def _image_mime_type(filename: str, content: bytes) -> str | None:
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return "image/webp"
        extension = Path(filename).suffix.lower()
        if extension == ".svg" or re.search(rb"<\s*svg\b", content[:4096], flags=re.IGNORECASE):
            return "image/svg+xml"
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(extension)
