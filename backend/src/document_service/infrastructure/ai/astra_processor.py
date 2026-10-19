import asyncio
import base64
import json
import logging
import re
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256

from openai import OpenAI

from document_service.application.ports.document_merger import (
    DocumentMerger,
    MergedDocumentResult,
    MergeSource,
)
from document_service.application.ports.document_processor import (
    AstraContractError,
    AstraRequestError,
    AstraResponseAudit,
    ProcessedAsset,
    ProcessedDocument,
)
from document_service.application.services.html_contract import (
    HtmlContractValidator,
    normalize_html,
    normalize_model_html,
)
from document_service.domain.value_objects.document_metadata import StyleSettings
from document_service.infrastructure.ai.docx_assets import DocxAssetExtractor
from document_service.infrastructure.ai.image_rasterizer import prepare_image_for_ai
from document_service.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AstraDocumentRequest:
    content: bytes
    style_reference_pdf: bytes
    style_prompt: str
    source_assets: list[ProcessedAsset]


class OpenAIAstraDocumentProcessor:
    def __init__(
        self,
        settings: Settings,
    ) -> None:
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.astra_request_timeout_seconds,
            max_retries=0,
        )
        self._model = settings.astra_model
        self._reasoning_effort = settings.astra_reasoning_effort
        self._edit_reasoning_effort = settings.astra_edit_reasoning_effort
        self._repair_reasoning_effort = settings.astra_repair_reasoning_effort
        self._repair_timeout_seconds = settings.astra_repair_timeout_seconds
        self._max_ai_file_input_bytes = settings.max_ai_file_input_bytes

    async def process(
        self,
        *,
        document_id: str,
        filename: str,
        content: bytes,
        theme_id: str,
        theme_version: str,
        style_settings: StyleSettings | None = None,
        custom_style_reference_pdf: bytes,
    ) -> ProcessedDocument:
        source_assets = DocxAssetExtractor().extract(document_id, content)
        if custom_style_reference_pdf is None:
            raise ValueError("A style reference PDF from object storage is required for Astra processing")
        style_reference_pdf = custom_style_reference_pdf
        style_prompt = self._read_style_prompt(style_settings or {})
        if not style_prompt or not style_prompt.strip():
            raise ValueError("A style prompt is required for Astra document processing")
        raw_model_response = await asyncio.to_thread(
            self._request,
            AstraDocumentRequest(
                content=content,
                style_reference_pdf=style_reference_pdf,
                style_prompt=style_prompt,
                source_assets=source_assets,
            ),
        )
        html = self._extract_html_response(raw_model_response)
        self._validate_full_document_html(html, HtmlContractValidator(None))
        source_digest = sha256(content).hexdigest()
        style_reference_digest = sha256(style_reference_pdf).hexdigest()
        pipeline_metadata = {
            "source_sha256": source_digest,
            "style_prompt_sha256": sha256(style_prompt.encode("utf-8")).hexdigest(),
            "style_reference_sha256": style_reference_digest,
            "visual_comparison": "disabled_html_only_output",
        }
        return ProcessedDocument(
            html=html,
            astra_html=html,
            language=self._detect_html_language(html),
            theme_id=theme_id,
            theme_version=theme_version,
            assets=source_assets,
            pipeline_metadata=pipeline_metadata,
            response_audit=getattr(self, "_last_response_audit", None),
        )

    async def edit_html(
        self,
        *,
        html: str,
        instruction: str,
        base_revision: int,
        block_hashes: dict[str, str],
        target_block_ids: list[str] | None,
        target_kind: str,
        target_asset_id: str | None,
        selected_text: str | None,
        theme_id: str,
        theme_version: str,
        style_prompt: str,
        style_reference_pdf: bytes,
    ) -> tuple[str, str]:
        raw_model_response = await asyncio.to_thread(
            self._request_html_edit,
            html,
            instruction,
            base_revision,
            block_hashes,
            target_block_ids,
            target_kind,
            target_asset_id,
            selected_text,
            theme_id,
            theme_version,
            style_prompt,
            style_reference_pdf,
        )
        HtmlContractValidator(None).validate(raw_model_response)
        return raw_model_response, "AI подготовил предложение изменений"

    async def edit_image(
        self,
        *,
        image: bytes,
        mime_type: str,
        filename: str,
        instruction: str,
        style_prompt: str,
        style_reference_pdf: bytes,
    ) -> bytes:
        return await asyncio.to_thread(
            self._request_image_edit,
            image,
            mime_type,
            filename,
            instruction,
            style_prompt,
            style_reference_pdf,
        )

    def _request(self, request: AstraDocumentRequest) -> str:
        file_inputs = [
            ("SOURCE_DOCUMENT.docx", request.content),
            ("STYLE_REFERENCE.pdf", request.style_reference_pdf),
        ]
        total_file_bytes = sum(len(data) for _, data in file_inputs)
        if total_file_bytes > self._max_ai_file_input_bytes:
            raise ValueError(
                "Combined SOURCE_DOCUMENT and STYLE_REFERENCE size "
                f"({total_file_bytes} bytes) exceeds the configured OpenAI file-input limit "
                f"({self._max_ai_file_input_bytes} bytes)"
            )

        uploaded_files = []
        try:
            for upload_filename, upload_content in file_inputs:
                uploaded_files.append(
                    self._client.files.create(
                        file=(upload_filename, upload_content),
                        purpose="user_data",
                    )
                )
            image_assets = [
                asset
                for asset in request.source_assets
                if asset.mime_type in {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
            ]
            asset_manifest = self._source_asset_manifest(image_assets)
            input_content: list[dict[str, object]] = [
                {"type": "input_file", "file_id": uploaded_files[0].id},
                {"type": "input_file", "file_id": uploaded_files[1].id},
            ]
            input_content.append(
                {
                    "type": "input_text",
                    "text": (
                        "SOURCE IMAGE MANIFEST. Use only these exact asset references in HTML. "
                        "Never use attachment://, file://, blob://, data:, http:// or https:// for image src.\n"
                        f"{asset_manifest or '(no supported source images)'}"
                    ),
                }
            )
            for index, asset in enumerate(image_assets, start=1):
                asset_content = base64.b64decode(asset.base64_data)
                asset_content, asset_mime_type = prepare_image_for_ai(asset_content, asset.mime_type, asset.filename)
                input_content.extend(
                    [
                        {
                            "type": "input_text",
                            "text": (
                                f"Source image image-{index:02d}: {asset.filename}. "
                                f"Use exactly src=\"asset://{asset.external_id}\" if this image is included."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:{asset_mime_type};base64,{base64.b64encode(asset_content).decode('ascii')}",
                            "detail": "high",
                        },
                    ]
                )
            input_content.append({"type": "input_text", "text": request.style_prompt})
            response = self._client.responses.create(
                model=self._model,
                reasoning={"effort": self._reasoning_effort},
                instructions=(
                    "Return only the requested editable HTML. Preserve relevant source images. "
                    "For source images, use only the exact asset:// references from the supplied "
                    "SOURCE IMAGE MANIFEST. Never emit attachment://image-NN or any other guessed "
                    "image URL. Do not invent asset identifiers."
                ),
                input=[
                    {
                        "role": "user",
                        "content": input_content,
                    }
                ],
                text={"format": {"type": "text"}},
            )
        except Exception as error:
            for uploaded in uploaded_files:
                with suppress(Exception):
                    self._client.files.delete(uploaded.id)
            audit = AstraResponseAudit(
                response_id=None,
                model=self._model,
                reasoning_effort=self._reasoning_effort,
                output_text=None,
                status="error",
                error_message=str(error),
            )
            self._last_response_audit = audit
            raise AstraRequestError(str(error), audit=audit) from error
        audit = AstraResponseAudit(
            response_id=getattr(response, "id", None),
            model=self._model,
            reasoning_effort=self._reasoning_effort,
            output_text=getattr(response, "output_text", None),
            status=getattr(response, "status", None) or "completed",
            usage=self._serialize_usage(getattr(response, "usage", None)),
        )
        self._last_response_audit = audit
        try:
            return self._validate_html_response(
                response,
                audit,
                asset_references=self._attachment_asset_references(image_assets),
                asset_manifest=asset_manifest,
            )
        finally:
            for uploaded in uploaded_files:
                with suppress(Exception):
                    self._client.files.delete(uploaded.id)
    @staticmethod
    def _extract_html_response(raw_response: str | None) -> str:
        html = (raw_response or "").strip()
        if not html:
            raise ValueError("OpenAI returned an empty HTML response")
        if html.startswith("```"):
            lines = html.splitlines()
            if lines and lines[0].strip().lower() in {"```", "```html"}:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            html = "\n".join(lines).strip()
        if not re.search(r"<[a-z][a-z0-9-]*(?:\s|>)", html, flags=re.IGNORECASE):
            raise ValueError("OpenAI response does not contain HTML")
        return html

    def _validate_html_response(
        self,
        response,
        audit: AstraResponseAudit,
        *,
        asset_references: dict[str, str] | None = None,
        asset_manifest: str | None = None,
    ) -> str:
        raw_response = getattr(response, "output_text", None)
        try:
            html = normalize_model_html(normalize_html(self._extract_html_response(raw_response)))
            html = self._rewrite_known_attachment_references(html, asset_references or {})
            HtmlContractValidator(None).validate(html)
            return html
        except (ValueError, TypeError) as error:
            invalid_audit = AstraResponseAudit(
                response_id=audit.response_id,
                model=audit.model,
                reasoning_effort=audit.reasoning_effort,
                output_text=audit.output_text,
                status="invalid",
                usage=audit.usage,
                error_message=str(error),
                created_at=audit.created_at,
            )
            self._last_response_audit = invalid_audit
            try:
                return self._repair_html_fragment(
                    raw_response or "",
                    str(error),
                    asset_references=asset_references or {},
                    asset_manifest=asset_manifest,
                )
            except Exception as repair_error:
                raise AstraContractError(
                    "GPT Astra 6 returned invalid HTML and the repair request also failed",
                    raw_responses=[item for item in (raw_response, str(repair_error)) if item],
                    validation_error=f"initial={error}; repair={repair_error}",
                    audit=invalid_audit,
                ) from repair_error

    def _repair_html_fragment(
        self,
        html: str,
        validation_error: str,
        *,
        asset_references: dict[str, str] | None = None,
        asset_manifest: str | None = None,
    ) -> str:
        logger.info("Astra HTML repair started validation_error=%s", validation_error)
        asset_references = asset_references or {}
        asset_manifest = asset_manifest or "(no source image manifest)"
        response = self._client.with_options(timeout=self._repair_timeout_seconds).responses.create(
            model=self._model,
            reasoning={"effort": self._repair_reasoning_effort},
            instructions=(
                "You repair HTML for a strict editable-document contract. Return only the corrected "
                "HTML fragment rooted in <article>. Preserve all text, images, links, tables and "
                "meaningful structure. Do not invent content. Remove or replace the violating "
                "construct. Never use <script>, <template>, <form>, <iframe>, <object>, <embed>, "
                "<applet>, <base>, event-handler attributes, external stylesheets or unsafe URLs. "
                "For images, preserve only exact asset:// references from the supplied manifest. "
                "Never use attachment://, file://, blob://, data:, http:// or https:// in image src. "
                f"Source image manifest:\n{asset_manifest}"
            ),
            input=(
                "Validation error:\n"
                f"{validation_error}\n\n"
                "HTML to repair:\n"
                f"{html}"
            ),
            text={"format": {"type": "text"}},
        )
        repaired = self._extract_html_response(getattr(response, "output_text", None))
        repaired = self._rewrite_known_attachment_references(repaired, asset_references)
        HtmlContractValidator(None).validate(repaired)
        logger.info("Astra HTML repair completed bytes=%s", len(repaired.encode("utf-8")))
        return repaired

    @staticmethod
    def _source_asset_manifest(assets: list[ProcessedAsset]) -> str:
        return "\n".join(
            f"image-{index:02d}: asset://{asset.external_id} "
            f"({asset.filename}, {asset.mime_type}, source pages: "
            f"{', '.join(map(str, asset.source_pages)) or 'unknown'})"
            for index, asset in enumerate(assets, start=1)
        )

    @staticmethod
    def _attachment_asset_references(assets: list[ProcessedAsset]) -> dict[str, str]:
        references: dict[str, str] = {}
        for index, asset in enumerate(assets, start=1):
            reference = f"asset://{asset.external_id}"
            references[f"image-{index:02d}"] = reference
            references[f"image-{index}"] = reference
            references[asset.filename] = reference
            references[asset.filename.lower()] = reference
        return references

    @staticmethod
    def _rewrite_known_attachment_references(html: str, references: dict[str, str]) -> str:
        if not references:
            return html

        pattern = re.compile(r"attachment://([^\"'\s>]+)", flags=re.IGNORECASE)

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            replacement = references.get(key) or references.get(key.lower())
            if replacement is None:
                return match.group(0)
            logger.warning("Rewriting unsupported image reference attachment://%s to %s", key, replacement)
            return replacement

        return pattern.sub(replace, html)

    @staticmethod
    def _detect_html_language(html: str) -> str:
        match = re.search(r"\blang\s*=\s*['\"]([a-zA-Z-]+)['\"]", html)
        return match.group(1) if match else "ru"

    def _read_style_prompt(self, style_settings: StyleSettings) -> str | None:
        prompt = style_settings.get("style_prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt
        return None

    @staticmethod
    def _validate_full_document_html(
        html: str,
        validator: HtmlContractValidator,
    ) -> None:
        validator.validate(html)

    def _request_html_edit(
        self,
        html: str,
        instruction: str,
        base_revision: int,
        block_hashes: dict[str, str],
        target_block_ids: list[str] | None,
        target_kind: str,
        target_asset_id: str | None,
        selected_text: str | None,
        theme_id: str,
        theme_version: str,
        style_prompt: str,
        style_reference_pdf: bytes,
    ) -> str:
        request_payload = {
            "base_revision": base_revision,
            "theme_id": theme_id,
            "theme_version": theme_version,
            "instruction": instruction,
            "target_block_ids": target_block_ids or [],
            "target_kind": target_kind,
            "target_asset_id": target_asset_id,
            "selected_text": selected_text,
            "block_hashes": block_hashes,
            "html": html,
        }
        inline_svg_instruction = ""
        if target_kind == "image" and (target_asset_id or "").startswith("inline-svg:"):
            inline_svg_index = (target_asset_id or "").split(":", 1)[1]
            inline_svg_instruction = (
                f" The selected image is the inline SVG at zero-based index {inline_svg_index} inside the selected block. "
                "Change only that SVG; "
                "preserve every other SVG, all text, layout and assets."
            )
        uploaded_reference = None
        try:
            uploaded_reference = self._client.files.create(
                file=("STYLE_REFERENCE.pdf", style_reference_pdf),
                purpose="user_data",
            )
            response = self._client.responses.create(
                model=self._model,
                reasoning={"effort": self._edit_reasoning_effort},
                instructions=(
                    "Edit the supplied HTML according to the user instruction and selected style. "
                    "Return only the complete resulting HTML document. "
                    "Preserve every unchanged block and all stable data-block-id/data-b attributes. "
                    "If target_kind is text, change only the selected text inside its block. "
                    "If target_kind is block, change only the selected blocks. "
                    "If target_kind is document, the whole document may be changed. "
                    f"{inline_svg_instruction} "
                    "Do not return a diff."
                ),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    f"Edit request:\n{json.dumps(request_payload, ensure_ascii=False)}"
                                    f"\n\nSelected style prompt:\n{style_prompt}"
                                    "\n\nReturn only HTML."
                                ),
                            },
                            {
                                "type": "input_text",
                                "text": "STYLE_REFERENCE.pdf: apply its visual language only.",
                            },
                            {"type": "input_file", "file_id": uploaded_reference.id, "detail": "high"},
                        ],
                    }
                ],
            )
        finally:
            if uploaded_reference is not None:
                with suppress(Exception):
                    self._client.files.delete(uploaded_reference.id)

        return self._validate_html_response(response, self._response_audit(response, self._edit_reasoning_effort))

    def _request_image_edit(
        self,
        image: bytes,
        mime_type: str,
        filename: str,
        instruction: str,
        style_prompt: str,
        style_reference_pdf: bytes,
    ) -> bytes:
        image, mime_type = prepare_image_for_ai(image, mime_type, filename)
        if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError("AI image editing supports SVG, PNG, JPEG and WebP images")
        total_size = len(image) + len(style_reference_pdf)
        if total_size > self._max_ai_file_input_bytes:
            raise ValueError(
                "Combined selected image and style reference size "
                f"({total_size} bytes) exceeds the configured OpenAI file-input limit "
                f"({self._max_ai_file_input_bytes} bytes)"
            )
        uploaded_reference = None
        image_data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
        try:
            uploaded_reference = self._client.files.create(
                file=("STYLE_REFERENCE.pdf", style_reference_pdf),
                purpose="user_data",
            )
            response = self._client.responses.create(
                model=self._model,
                reasoning={"effort": self._edit_reasoning_effort},
                instructions=(
                    "Edit only the supplied image according to the user instruction. "
                    "Preserve the subject identity and useful details unless the instruction says otherwise. "
                    "Use STYLE_REFERENCE.pdf and the selected style prompt only as visual guidance. "
                    "Return one edited image through the image_generation tool; do not return HTML or text."
                ),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    f"Image filename: {filename}\n"
                                    f"User instruction: {instruction}\n\n"
                                    f"Selected style prompt:\n{style_prompt}\n\n"
                                    "STYLE_REFERENCE.pdf is visual guidance only; do not copy its text or objects."
                                ),
                            },
                            {"type": "input_image", "image_url": image_data_url, "detail": "high"},
                            {"type": "input_file", "file_id": uploaded_reference.id},
                        ],
                    }
                ],
                tools=[
                    {
                        "type": "image_generation",
                        "input_fidelity": "high",
                        "output_format": "png",
                        "quality": "high",
                    }
                ],
            )
            result = next(
                (
                    getattr(item, "result", None)
                    for item in getattr(response, "output", [])
                    if getattr(item, "type", None) == "image_generation_call"
                ),
                None,
            )
            if not result:
                raise ValueError("GPT Astra 6 did not return an edited image")
            try:
                return base64.b64decode(result, validate=True)
            except ValueError as error:
                raise ValueError("GPT Astra 6 returned an invalid image result") from error
        finally:
            if uploaded_reference is not None:
                with suppress(Exception):
                    self._client.files.delete(uploaded_reference.id)

    @staticmethod
    def _serialize_usage(usage) -> dict[str, object]:
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            return usage.model_dump(mode="json")
        if isinstance(usage, dict):
            return usage
        return {"repr": repr(usage)}

    def _response_audit(self, response, reasoning_effort: str) -> AstraResponseAudit:
        audit = AstraResponseAudit(
            response_id=getattr(response, "id", None),
            model=self._model,
            reasoning_effort=reasoning_effort,
            output_text=getattr(response, "output_text", None),
            status=getattr(response, "status", None) or "completed",
            usage=self._serialize_usage(getattr(response, "usage", None)),
        )
        self._last_response_audit = audit
        return audit


class OpenAIAstraDocumentMerger(DocumentMerger):
    def __init__(
        self,
        settings: Settings,
    ) -> None:
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.astra_request_timeout_seconds,
            max_retries=0,
        )
        self._model = settings.astra_model
        self._reasoning_effort = settings.astra_reasoning_effort
        self._max_ai_file_input_bytes = settings.max_ai_file_input_bytes

    async def merge(
        self,
        *,
        document_id: str,
        sources: list[MergeSource],
        merge_notes: str | None,
        theme_id: str,
        theme_version: str,
        style_prompt: str,
        style_reference_pdf: bytes,
    ) -> MergedDocumentResult:
        source_assets: list[ProcessedAsset] = []
        for source in sources:
            assets = [
                ProcessedAsset(
                    external_id=f"{source.source_file_id}-{asset.external_id}",
                    filename=asset.filename,
                    mime_type=asset.mime_type,
                    base64_data=asset.base64_data,
                    width=asset.width,
                    height=asset.height,
                    alt=f"{asset.alt} ({source.filename})".strip(),
                    source_pages=asset.source_pages,
                )
                for asset in DocxAssetExtractor().extract(
                    f"{document_id}|{source.source_file_id}",
                    source.content,
                )
            ]
            source_assets.extend(assets)
        raw_model_response = await asyncio.to_thread(
            self._request_merge,
            document_id,
            sources,
            merge_notes,
            style_prompt,
            style_reference_pdf,
            theme_id,
            theme_version,
            source_assets,
        )
        return MergedDocumentResult(
            html=raw_model_response,
            astra_html=raw_model_response,
            language=OpenAIAstraDocumentProcessor._detect_html_language(raw_model_response),
            theme_id=theme_id,
            theme_version=theme_version,
            assets=source_assets,
            warnings=[],
        )

    def _request_merge(
        self,
        document_id: str,
        sources: list[MergeSource],
        merge_notes: str | None,
        style_prompt: str,
        style_reference_pdf: bytes,
        theme_id: str,
        theme_version: str,
        source_assets: list[ProcessedAsset],
    ) -> str:
        file_inputs: list[tuple[str, bytes]] = []
        for source in sources:
            prefix = f"SOURCE_{source.position:02d}"
            file_inputs.append((f"{prefix}_{source.filename}", source.content))
        file_inputs.append(("STYLE_REFERENCE.pdf", style_reference_pdf))
        total_file_bytes = sum(len(data) for _, data in file_inputs)
        if total_file_bytes > self._max_ai_file_input_bytes:
            raise ValueError(
                "Combined merge sources, renders and style reference size "
                f"({total_file_bytes} bytes) exceeds the configured OpenAI file-input limit "
                f"({self._max_ai_file_input_bytes} bytes)"
            )

        uploaded_files = []
        source_manifest = "\n".join(
            f"{source.position}. {source.filename} (source_file_id={source.source_file_id})" for source in sources
        )
        source_asset_manifest = "\n".join(
            f"{index}. asset://{asset.external_id} ({asset.filename}, {asset.mime_type}, "
            f"source pages: {', '.join(map(str, asset.source_pages)) or 'unknown'})"
            for index, asset in enumerate(source_assets, start=1)
        )
        reference_digest = sha256(style_reference_pdf).hexdigest()[:16]
        prompt = (
            "Merge the supplied DOCX files into one coherent editable HTML manual. "
            "Use the selected style prompt and STYLE_REFERENCE.pdf for visual language only. "
            "Preserve source facts, text and images. Return only the complete HTML document.\n\n"
            f"Document id: {document_id}. Theme: {theme_id}@{theme_version}.\n"
            f"Style reference version: sha256:{reference_digest}.\n"
            f"User merge notes: {merge_notes or '(none)'}\n\n"
            f"Selected style prompt from the published style:\n{style_prompt}\n\n"
            "Source files in user-provided order:\n"
            f"{source_manifest}\n\n"
            "Input roles are strict: SOURCE DOCX files contain source content. "
            "STYLE_REFERENCE.pdf contains visual guidance only. Never "
            "copy text, facts, product names, images or page numbers from the style reference.\n"
            "Use source image assets directly with their asset:// ids. Do not copy source images "
            "into the response as inline replacements.\n"
            "Source image manifest:\n"
            f"{source_asset_manifest or '(no supported embedded images)'}"
        )
        instructions = (
            "Merge the user-provided DOCX files into one editable HTML document. "
            "The style prompt and STYLE_REFERENCE.pdf are the only style sources. "
            "Do not copy content from the reference PDF. Return only HTML."
        )
        try:
            for upload_filename, upload_content in file_inputs:
                uploaded_files.append(
                    self._client.files.create(
                        file=(upload_filename, upload_content),
                        purpose="user_data",
                    )
                )

            input_content: list[dict[str, object]] = []
            uploaded_index = 0
            for source in sources:
                input_content.extend(
                    [
                        {
                            "type": "input_text",
                            "text": (
                                f"SOURCE_{source.position:02d} DOCX: authoritative source "
                                f"content for {source.filename}."
                            ),
                        },
                        {"type": "input_file", "file_id": uploaded_files[uploaded_index].id},
                    ]
                )
                uploaded_index += 1
            input_content.extend(
                [
                    {
                        "type": "input_text",
                        "text": (
                            "STYLE_REFERENCE.pdf: visual style only. Never reuse its text, "
                            "facts, product names, images or page numbers."
                        ),
                    },
                    {
                        "type": "input_file",
                        "file_id": uploaded_files[uploaded_index].id,
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
                            "image_url": (f"data:{asset.mime_type};base64,{asset.base64_data}"),
                            "detail": "high",
                        },
                    ]
                )
            response = self._client.responses.create(
                model=self._model,
                reasoning={"effort": self._reasoning_effort},
                instructions=instructions,
                input=[
                    {
                        "role": "user",
                        "content": input_content,
                    }
                ],
            )
            return OpenAIAstraDocumentProcessor._validate_html_response(
                self,
                response,
                OpenAIAstraDocumentProcessor._response_audit(self, response, self._reasoning_effort),
            )
        finally:
            for uploaded in uploaded_files:
                with suppress(Exception):
                    self._client.files.delete(uploaded.id)
