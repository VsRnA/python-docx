import asyncio
import base64
import json
import mimetypes
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from openai import OpenAI
from pydantic import ValidationError

from document_service.application.ports.document_ai_editor import (
    ChangeOperation,
    DocumentChangeSet,
)
from document_service.application.ports.document_converter import DocumentPdfConverter
from document_service.application.ports.document_processor import (
    ProcessedAsset,
    ProcessedDocument,
)
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.infrastructure.ai.contracts import (
    AstraChangeSetResponse,
    AstraFullDocumentResponse,
)
from document_service.infrastructure.ai.prompt_package import PromptPackageLoader
from document_service.infrastructure.config.settings import Settings


class OpenAIAstraDocumentProcessor:
    def __init__(
        self,
        settings: Settings,
        prompt_root: Path,
        *,
        source_pdf_converter: DocumentPdfConverter | None = None,
    ) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.astra_model
        self._prompts = PromptPackageLoader(prompt_root)
        self._source_pdf_converter = source_pdf_converter
        self._style_reference_pdf_path = Path(settings.style_reference_pdf_path)
        self._style_reference_overview_dir = Path(settings.style_reference_overview_dir)
        self._max_ai_file_input_bytes = settings.max_ai_file_input_bytes

    async def process(
        self,
        *,
        document_id: str,
        filename: str,
        content: bytes,
        prompt_package_version: str,
        theme_id: str,
        theme_version: str,
    ) -> ProcessedDocument:
        if self._source_pdf_converter is None:
            raise RuntimeError("A DOCX-to-PDF converter is required for initial document import")
        package = self._prompts.load_full_document(prompt_package_version)
        source_assets = self._extract_docx_assets(document_id, content)
        source_pdf = await self._source_pdf_converter.convert_docx(
            filename=filename,
            content=content,
        )
        style_reference_pdf = self._read_style_reference_pdf()
        style_overviews = self._read_style_overviews()
        raw = await asyncio.to_thread(
            self._request,
            filename,
            content,
            source_pdf,
            style_reference_pdf,
            style_overviews,
            document_id,
            package.system,
            package.task,
            package.schema,
            package.components,
            package.classes,
            theme_id,
            theme_version,
            source_assets,
        )
        payload = AstraFullDocumentResponse.model_validate_json(raw)
        if payload.document.document_id != document_id:
            raise RuntimeError("GPT Astra 6 returned another document identifier")
        if payload.document.theme_id != theme_id or payload.document.theme_version != theme_version:
            raise RuntimeError("GPT Astra 6 returned an unrequested document theme")
        return ProcessedDocument(
            html=payload.document.html,
            astra_html=payload.document.html,
            language=payload.document.language,
            theme_id=payload.document.theme_id,
            theme_version=payload.document.theme_version,
            assets=source_assets + [
                ProcessedAsset(
                    external_id=asset.asset_id,
                    filename=asset.filename,
                    mime_type=asset.mime_type,
                    base64_data=asset.data,
                    width=asset.width,
                    height=asset.height,
                    alt=asset.alt,
                )
                for asset in payload.document.assets
            ],
            warnings=payload.warnings,
        )

    async def edit(
        self,
        *,
        html: str,
        instruction: str,
        base_revision: int,
        block_hashes: dict[str, str],
        prompt_package_version: str,
        theme_id: str,
        theme_version: str,
    ) -> DocumentChangeSet:
        package = self._prompts.load_change_set(prompt_package_version)
        raw = await asyncio.to_thread(
            self._request_change_set,
            html,
            instruction,
            base_revision,
            block_hashes,
            package.system,
            package.task,
            package.schema,
            package.components,
            package.classes,
            theme_id,
            theme_version,
        )
        payload = AstraChangeSetResponse.model_validate_json(raw).change_set
        return DocumentChangeSet(
            base_revision=payload.base_revision,
            summary=payload.summary,
            operations=[
                ChangeOperation(
                    operation=item.operation,
                    block_id=item.block_id,
                    expected_hash=item.expected_hash,
                    html=item.html,
                )
                for item in payload.operations
            ],
            assets=[
                ProcessedAsset(
                    external_id=item.asset_id,
                    filename=item.filename,
                    mime_type=item.mime_type,
                    base64_data=item.data,
                    width=item.width,
                    height=item.height,
                    alt=item.alt,
                )
                for item in payload.assets
            ],
        )

    def _request(
        self,
        filename: str,
        content: bytes,
        source_pdf: bytes,
        style_reference_pdf: bytes,
        style_overviews: list[tuple[str, str, bytes]],
        document_id: str,
        system: str,
        task: str,
        schema: str,
        components: str,
        classes: str,
        theme_id: str,
        theme_version: str,
        source_assets: list[ProcessedAsset],
    ) -> str:
        file_inputs = [
            ("SOURCE_DOCUMENT.docx", content),
            ("SOURCE_RENDER.pdf", source_pdf),
            ("STYLE_REFERENCE.pdf", style_reference_pdf),
        ]
        total_file_bytes = sum(len(data) for _, data in file_inputs)
        if total_file_bytes > self._max_ai_file_input_bytes:
            raise ValueError(
                "Combined SOURCE_DOCUMENT, SOURCE_RENDER and STYLE_REFERENCE size "
                f"({total_file_bytes} bytes) exceeds the configured OpenAI file-input limit "
                f"({self._max_ai_file_input_bytes} bytes)"
            )

        uploaded_files = []
        source_asset_manifest = "\n".join(
            f"{index}. asset://{asset.external_id} ({asset.filename}, {asset.mime_type}, "
            f"source pages: {', '.join(map(str, asset.source_pages)) or 'unknown'})"
            for index, asset in enumerate(source_assets, start=1)
        )
        reference_digest = sha256(style_reference_pdf).hexdigest()[:16]
        prompt = (
            f"{task}\n\nDocument id: {document_id}. Original filename: {filename}. "
            f"Theme: {theme_id}@{theme_version}.\n"
            f"Style reference version: sha256:{reference_digest}.\n"
            "Input roles are strict: SOURCE_DOCUMENT.docx and SOURCE_RENDER.pdf contain source "
            "content. STYLE_REFERENCE.pdf and STYLE_OVERVIEW images contain visual guidance only. "
            "Never copy content from the style reference.\n"
            "The images following this instruction were extracted from the DOCX in their document "
            "order. Place every supplied source image in the HTML at its corresponding location. "
            "Reference it directly using its asset:// id. Do not copy source images into the JSON "
            "assets array; that array is only for newly generated or flattened replacement "
            "images.\n"
            "Source image manifest:\n"
            f"{source_asset_manifest or '(no supported embedded images)'}\n\n"
            f"Approved component templates:\n{components}\n\n"
            f"Approved CSS classes (one per line):\n{classes}\n\n"
            f"Return JSON matching this schema exactly:\n{schema}"
        )
        try:
            for upload_filename, upload_content in file_inputs:
                uploaded_files.append(
                    self._client.files.create(
                        file=(upload_filename, upload_content),
                        purpose="user_data",
                    )
                )

            input_content: list[dict[str, object]] = [
                {
                    "type": "input_text",
                    "text": "SOURCE_DOCUMENT.docx: authoritative text and editable structure.",
                },
                {"type": "input_file", "file_id": uploaded_files[0].id},
                {
                    "type": "input_text",
                    "text": (
                        "SOURCE_RENDER.pdf: authoritative visual rendering of the same source "
                        "document, including pages, images, arrows and anchored labels."
                    ),
                },
                {
                    "type": "input_file",
                    "file_id": uploaded_files[1].id,
                    "detail": "high",
                },
                {
                    "type": "input_text",
                    "text": (
                        "STYLE_REFERENCE.pdf: visual style only. Never reuse its text, facts, "
                        "product names, images or page numbers."
                    ),
                },
                {
                    "type": "input_file",
                    "file_id": uploaded_files[2].id,
                    "detail": "high",
                },
            ]
            for overview_filename, overview_mime_type, overview_content in style_overviews:
                input_content.extend(
                    [
                        {
                            "type": "input_text",
                            "text": (
                                f"STYLE_OVERVIEW {overview_filename}: page-system overview only; "
                                "never treat visible words or illustrations as source content."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{overview_mime_type};base64,"
                                f"{base64.b64encode(overview_content).decode('ascii')}"
                            ),
                            "detail": "high",
                        },
                    ]
                )
            input_content.append({"type": "input_text", "text": prompt})
            for asset in source_assets:
                input_content.extend(
                    [
                        {
                            "type": "input_text",
                            "text": (
                                f"Source image asset://{asset.external_id} ({asset.filename}); "
                                f"DOCX pages: {', '.join(map(str, asset.source_pages)) or 'unknown'}"
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{asset.mime_type};base64,{asset.base64_data}"
                            ),
                            "detail": "high",
                        },
                    ]
                )
            response = self._client.responses.create(
                model=self._model,
                instructions=system,
                input=[
                    {
                        "role": "user",
                        "content": input_content,
                    }
                ],
            )
            validator = HtmlContractValidator(set(classes.splitlines()))
            return self._repair_until_valid(
                response,
                schema,
                AstraFullDocumentResponse,
                html_validator=lambda payload: self._validate_full_document_html(
                    payload.document.html,
                    validator,
                    source_assets,
                ),
            )
        finally:
            for uploaded in uploaded_files:
                try:
                    self._client.files.delete(uploaded.id)
                except Exception:
                    # Remote temporary-file cleanup must not invalidate a completed import.
                    pass

    def _read_style_reference_pdf(self) -> bytes:
        try:
            content = self._style_reference_pdf_path.read_bytes()
        except FileNotFoundError as error:
            raise RuntimeError(
                f"Style reference PDF was not found: {self._style_reference_pdf_path}"
            ) from error
        if not content.startswith(b"%PDF-"):
            raise RuntimeError(
                f"Style reference is not a valid PDF: {self._style_reference_pdf_path}"
            )
        return content

    def _read_style_overviews(self) -> list[tuple[str, str, bytes]]:
        if not self._style_reference_overview_dir.exists():
            return []
        overviews: list[tuple[str, str, bytes]] = []
        for path in sorted(self._style_reference_overview_dir.iterdir()):
            if not path.is_file():
                continue
            mime_type, _ = mimetypes.guess_type(path.name)
            if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
                continue
            overviews.append((path.name, mime_type, path.read_bytes()))
        return overviews

    @staticmethod
    def _extract_docx_assets(document_id: str, content: bytes) -> list[ProcessedAsset]:
        """Extract meaningful embedded images while keeping the DOCX as the primary AI input."""
        try:
            with ZipFile(BytesIO(content)) as archive:
                media_names = [
                    name
                    for name in archive.namelist()
                    if name.startswith("word/media/") and not name.endswith("/")
                ]
                ordered_media = OpenAIAstraDocumentProcessor._ordered_media_with_pages(
                    archive, media_names
                )
                assets: list[ProcessedAsset] = []
                for name, source_pages in ordered_media:
                    image = archive.read(name)
                    mime_type = OpenAIAstraDocumentProcessor._image_mime_type(name, image)
                    # DOCX often contains hundreds of tiny DrawingML fragments. They are not
                    # useful as standalone figures and overwhelm multimodal requests.
                    if mime_type is None or len(image) < 2_048:
                        continue
                    filename = Path(name).name
                    asset_id = str(uuid5(NAMESPACE_URL, f"{document_id}|{name}"))
                    assets.append(
                        ProcessedAsset(
                            external_id=asset_id,
                            filename=filename,
                            mime_type=mime_type,
                            base64_data=base64.b64encode(image).decode("ascii"),
                            alt=(
                                "Изображение из исходного документа: "
                                f"{filename}"
                            ),
                            source_pages=tuple(source_pages),
                        )
                    )
                return assets
        except (BadZipFile, KeyError, ElementTree.ParseError):
            return []

    @staticmethod
    def _ordered_media_with_pages(
        archive: ZipFile, media_names: list[str]
    ) -> list[tuple[str, list[int]]]:
        rels_name = "word/_rels/document.xml.rels"
        document_name = "word/document.xml"
        if rels_name not in archive.namelist() or document_name not in archive.namelist():
            return [(name, []) for name in sorted(media_names)]

        relationships = ElementTree.fromstring(archive.read(rels_name))
        rel_targets = {
            relation.attrib.get("Id", ""): relation.attrib.get("Target", "")
            for relation in relationships
        }
        document = ElementTree.fromstring(archive.read(document_name))
        relationship_attribute = (
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
        )
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
    def _validate_full_document_html(
        html: str,
        validator: HtmlContractValidator,
        source_assets: list[ProcessedAsset],
    ) -> None:
        """Keep model-selected composition, but require complete source-asset coverage."""
        validator.validate(html)
        missing = [
            asset.external_id
            for asset in source_assets
            if f"asset://{asset.external_id}" not in html
        ]
        if missing:
            raise ValueError(
                "The HTML omits source assets: " + ", ".join(missing[:20])
            )

    @staticmethod
    def _image_mime_type(filename: str, content: bytes) -> str | None:
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return "image/webp"
        guessed, _ = mimetypes.guess_type(filename)
        return guessed if guessed in {"image/png", "image/jpeg", "image/webp"} else None

    def _request_change_set(
        self,
        html: str,
        instruction: str,
        base_revision: int,
        block_hashes: dict[str, str],
        system: str,
        task: str,
        schema: str,
        components: str,
        classes: str,
        theme_id: str,
        theme_version: str,
    ) -> str:
        request_payload = {
            "base_revision": base_revision,
            "theme_id": theme_id,
            "theme_version": theme_version,
            "instruction": instruction,
            "block_hashes": block_hashes,
            "html": html,
        }
        response = self._client.responses.create(
            model=self._model,
            instructions=system,
            input=(
                f"{task}\n\nRequest:\n{json.dumps(request_payload, ensure_ascii=False)}"
                f"\n\nApproved component templates:\n{components}"
                f"\n\nApproved CSS classes (one per line):\n{classes}"
                f"\n\nReturn JSON matching this schema exactly:\n{schema}"
            ),
        )
        validator = HtmlContractValidator(set(classes.splitlines()))

        def validate_changes(payload: AstraChangeSetResponse) -> None:
            for operation in payload.change_set.operations:
                if operation.html:
                    validator.validate(operation.html)

        return self._repair_until_valid(
            response,
            schema,
            AstraChangeSetResponse,
            html_validator=validate_changes,
        )

    def _repair_until_valid(self, response, schema: str, contract_type, html_validator=None) -> str:
        for attempt in range(3):
            if not response.output_text:
                validation_error = "The response was empty."
            else:
                try:
                    json.loads(response.output_text)
                    payload = contract_type.model_validate_json(response.output_text)
                    if html_validator:
                        html_validator(payload)
                    return response.output_text
                except (json.JSONDecodeError, ValidationError, ValueError) as error:
                    validation_error = str(error)
            if attempt == 2:
                break
            response = self._client.responses.create(
                model=self._model,
                previous_response_id=response.id,
                input=(
                    "Repair your previous response. Return only valid JSON and do not change valid "
                    f"document content. Validation error:\n{validation_error}\nSchema:\n{schema}"
                ),
            )
        raise RuntimeError("GPT Astra 6 failed the response contract after two repair attempts")
