import re
from html.parser import HTMLParser
from pathlib import PurePosixPath
from uuid import UUID

from document_service.application.errors import OutsideSelectionError, SelectionNotFoundError
from document_service.application.ports.document_ai_editor import DocumentAiEditor
from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.services.change_set import ChangeSetApplier, HtmlBlockIndex
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.services.html_blocks import ensure_block_ids
from document_service.application.use_cases.save_document import RevisionConflictError
from document_service.domain.entities.asset import Asset


class EditDocumentWithAi:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        assets: AssetRepository,
        storage: ObjectStorage,
        editor: DocumentAiEditor,
        validator: HtmlContractValidator,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._assets = assets
        self._storage = storage
        self._editor = editor
        self._validator = validator
        self._changes = ChangeSetApplier()

    async def propose(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        base_revision: int,
        instruction: str,
        target_block_ids: list[str] | None = None,
        target: dict | None = None,
    ) -> dict:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        if document.current_revision != base_revision:
            raise RevisionConflictError(
                f"Expected revision {base_revision}, current revision is {document.current_revision}"
            )
        style_prompt = document.style_settings.get("style_prompt")
        if not isinstance(style_prompt, str) or not style_prompt.strip():
            raise ValueError("Published style prompt is not attached to the document")
        reference = document.style_settings.get("reference_file")
        if not isinstance(reference, dict) or not isinstance(reference.get("key"), str):
            raise ValueError("Published style reference PDF is not attached to the document")
        style_reference_pdf = await self._storage.get(key=reference["key"])
        version = await self._versions.get_current(document_id)
        if version is None:
            raise ValueError("Document has no editable version")
        if not instruction.strip():
            raise ValueError("AI edit instruction must not be empty")
        normalized_html = ensure_block_ids(version.html)
        if normalized_html != version.html:
            version.html = normalized_html
            if version.astra_html:
                version.astra_html = ensure_block_ids(version.astra_html)
            await self._versions.update(version)
        block_hashes = self._changes.block_hashes(version.html)
        target = target or {}
        target_kind = target.get("kind", "document")
        if target_kind not in {"document", "block", "text", "image"}:
            raise ValueError("Unknown AI edit target")
        target_block_id = target.get("block_id")
        if target_block_id and target_block_id not in (target_block_ids or []):
            target_block_ids = [*(target_block_ids or []), target_block_id]
        normalized_target_block_ids = list(dict.fromkeys(target_block_ids or []))
        unknown_block_ids = [block_id for block_id in normalized_target_block_ids if block_id not in block_hashes]
        if unknown_block_ids:
            raise SelectionNotFoundError("Selected blocks were not found: " + ", ".join(unknown_block_ids[:10]))
        if target_kind == "image":
            return await self._propose_image_edit(
                document=document,
                html=version.html,
                instruction=instruction.strip(),
                style_prompt=style_prompt,
                style_reference_pdf=style_reference_pdf,
                target=target,
                target_block_ids=normalized_target_block_ids,
                svg_index=target.get("svg_index") if isinstance(target.get("svg_index"), int) else None,
                theme_id=version.theme_id,
                theme_version=version.theme_version,
            )
        changed_html, summary = await self._editor.edit_html(
            html=version.html,
            instruction=instruction.strip(),
            base_revision=base_revision,
            block_hashes=block_hashes,
            target_block_ids=normalized_target_block_ids or None,
            target_kind=target_kind,
            target_asset_id=str(target.get("asset_id")) if target.get("asset_id") else None,
            selected_text=target.get("selected_text") if isinstance(target.get("selected_text"), str) else None,
            theme_id=version.theme_id,
            theme_version=version.theme_version,
            style_prompt=style_prompt,
            style_reference_pdf=style_reference_pdf,
        )
        if normalized_target_block_ids:
            changed_hashes = self._changes.block_hashes(changed_html)
            allowed = set(normalized_target_block_ids)
            if any(block_id not in allowed and changed_hashes.get(block_id) != digest for block_id, digest in block_hashes.items()):
                raise OutsideSelectionError("AI edit changed blocks outside the selected area")
        if target_kind == "text" and target.get("selected_text") and len(normalized_target_block_ids) == 1:
            self._ensure_only_selected_text_changed(
                version.html,
                changed_html,
                normalized_target_block_ids[0],
                str(target["selected_text"]),
            )
        return {
            "base_revision": base_revision,
            "summary": summary or "AI подготовил предложение изменений",
            "before_html": version.html,
            "after_html": changed_html,
            "operations": [],
        }

    @staticmethod
    def _plain_text(html: str) -> str:
        class TextParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__(convert_charrefs=True)
                self.parts: list[str] = []

            def handle_data(self, data: str) -> None:
                self.parts.append(data)

        parser = TextParser()
        parser.feed(html)
        parser.close()
        return " ".join(" ".join(parser.parts).split())

    def _ensure_only_selected_text_changed(
        self,
        before_html: str,
        after_html: str,
        block_id: str,
        selected_text: str,
    ) -> None:
        before_block = HtmlBlockIndex().build(before_html).get(block_id)
        after_block = HtmlBlockIndex().build(after_html).get(block_id)
        if before_block is None or after_block is None:
            raise OutsideSelectionError("AI removed the selected text block")
        before_text = self._plain_text(before_block.html)
        after_text = self._plain_text(after_block.html)
        selected = " ".join(selected_text.split())
        start = before_text.find(selected)
        if start < 0:
            raise SelectionNotFoundError("Selected text was not found in the document block")
        prefix = before_text[:start]
        suffix = before_text[start + len(selected):]
        if not after_text.startswith(prefix) or not after_text.endswith(suffix):
            raise OutsideSelectionError("AI changed text outside the selected fragment")

    async def _propose_image_edit(
        self,
        *,
        document,
        html: str,
        instruction: str,
        style_prompt: str,
        style_reference_pdf: bytes,
        target: dict,
        target_block_ids: list[str],
        svg_index: int | None,
        theme_id: str,
        theme_version: str,
    ) -> dict:
        asset_id_value = target.get("asset_id")
        if not asset_id_value:
            return await self._propose_inline_svg_edit(
                document=document,
                html=html,
                instruction=instruction,
                style_prompt=style_prompt,
                style_reference_pdf=style_reference_pdf,
                target_block_ids=target_block_ids,
                svg_index=svg_index,
                theme_id=theme_id,
                theme_version=theme_version,
            )
        try:
            asset_id = UUID(str(asset_id_value))
        except ValueError as error:
            raise SelectionNotFoundError("Selected image has an invalid asset identifier") from error
        asset = await self._assets.get(asset_id)
        if asset is None or asset.document_id != document.id:
            raise SelectionNotFoundError("Selected image was not found in this document")
        if len(target_block_ids) != 1:
            raise SelectionNotFoundError("Select exactly one image inside one document block")
        block = HtmlBlockIndex().build(html).get(target_block_ids[0])
        if block is None:
            raise SelectionNotFoundError("Selected image block was not found")
        old_reference = f"asset://{asset.id}"
        if old_reference not in block.html:
            raise SelectionNotFoundError("Selected image is not present in the selected block")
        image = await self._storage.get(key=asset.storage_key)
        edited_image = await self._editor.edit_image(
            image=image,
            mime_type=asset.mime_type,
            filename=asset.filename,
            instruction=instruction,
            style_prompt=style_prompt,
            style_reference_pdf=style_reference_pdf,
        )
        if not edited_image:
            raise ValueError("AI returned an empty edited image")
        filename_stem = PurePosixPath(asset.filename).stem or "image"
        filename = f"{filename_stem}-ai-edit.png"
        stored = await self._storage.put(
            key=f"documents/{document.id}/assets/ai-{asset_id}-{filename}",
            content=edited_image,
            content_type="image/png",
        )
        new_asset = Asset(
            document_id=document.id,
            storage_key=stored.key,
            mime_type="image/png",
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            filename=filename,
            alt=asset.alt,
        )
        await self._assets.add_many([new_asset])
        new_reference = f"asset://{new_asset.id}"
        replacement = block.html.replace(old_reference, new_reference, 1)
        changed_html = html[:block.start] + replacement + html[block.end:]
        return {
            "base_revision": document.current_revision,
            "summary": "AI обработал выбранное изображение",
            "before_html": html,
            "after_html": changed_html,
            "operations": [{"operation": "replace_image", "asset_id": str(new_asset.id)}],
        }

    async def _propose_inline_svg_edit(
        self,
        *,
        document,
        html: str,
        instruction: str,
        style_prompt: str,
        style_reference_pdf: bytes,
        target_block_ids: list[str],
        svg_index: int | None,
        theme_id: str,
        theme_version: str,
    ) -> dict:
        if len(target_block_ids) != 1 or svg_index is None:
            raise SelectionNotFoundError("Select exactly one inline SVG image inside one document block")
        selected_block_id = target_block_ids[0]
        block = HtmlBlockIndex().build(html).get(selected_block_id)
        if block is None:
            raise SelectionNotFoundError("Selected SVG block was not found")
        before_svgs = self._inline_svg_fragments(block.html)
        if svg_index >= len(before_svgs):
            raise SelectionNotFoundError("Selected SVG image was not found in the document block")
        changed_html, summary = await self._editor.edit_html(
            html=html,
            instruction=instruction,
            base_revision=document.current_revision,
            block_hashes=self._changes.block_hashes(html),
            target_block_ids=[selected_block_id],
            target_kind="image",
            target_asset_id=f"inline-svg:{svg_index}",
            selected_text=None,
            theme_id=theme_id,
            theme_version=theme_version,
            style_prompt=style_prompt,
            style_reference_pdf=style_reference_pdf,
        )
        after_block = HtmlBlockIndex().build(changed_html).get(selected_block_id)
        if after_block is None:
            raise OutsideSelectionError("AI removed the selected SVG block")
        after_svgs = self._inline_svg_fragments(after_block.html)
        before_projection = re.sub(r"\s+", " ", self._without_inline_svg(block.html, svg_index)).strip()
        after_projection = re.sub(r"\s+", " ", self._without_inline_svg(after_block.html, svg_index)).strip()
        if len(after_svgs) != len(before_svgs) or before_projection != after_projection:
            raise OutsideSelectionError("AI changed another SVG or the SVG structure outside the selected image")
        before_hashes = self._changes.block_hashes(html)
        after_hashes = self._changes.block_hashes(changed_html)
        if any(
            other_block_id != selected_block_id
            and after_hashes.get(other_block_id) != digest
            for other_block_id, digest in before_hashes.items()
        ):
            raise OutsideSelectionError("AI changed a block outside the selected SVG image")
        return {
            "base_revision": document.current_revision,
            "summary": summary or "AI обработал выбранное SVG-изображение",
            "before_html": html,
            "after_html": changed_html,
            "operations": [{"operation": "replace_svg", "block_id": selected_block_id, "svg_index": svg_index}],
        }

    @staticmethod
    def _inline_svg_fragments(html: str) -> list[str]:
        return re.findall(r"<svg\b[^>]*>.*?</svg\s*>", html, flags=re.IGNORECASE | re.DOTALL)

    @staticmethod
    def _without_inline_svg(html: str, selected_index: int) -> str:
        matches = list(re.finditer(r"<svg\b[^>]*>.*?</svg\s*>", html, flags=re.IGNORECASE | re.DOTALL))
        if selected_index >= len(matches):
            return html
        match = matches[selected_index]
        return html[:match.start()] + "__SELECTED_SVG__" + html[match.end():]
