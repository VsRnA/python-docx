import json
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.ports.style_repository import StyleData, StyleRepository, StyleVersionData
from document_service.application.services.style_validation import validate_style_settings
from document_service.domain.value_objects.document_metadata import StyleSettings


class StyleManagement:
    def __init__(self, repository: StyleRepository, *, default_theme_id: str, default_theme_version: str) -> None:
        self._repository = repository
        self._default_theme_id = default_theme_id
        self._default_theme_version = default_theme_version

    def default_settings(self) -> StyleSettings:
        return {
            "renderer_theme_id": self._default_theme_id,
            "renderer_theme_version": self._default_theme_version,
            "editor_contract": "semantic-document-v1",
        }

    @staticmethod
    def manifest(settings: StyleSettings) -> dict:
        return {
            "settings": settings,
            "renderer_theme": {
                "id": settings.get("renderer_theme_id"),
                "version": settings.get("renderer_theme_version"),
            },
            "schema_version": "1",
        }

    async def list(self, owner_id: UUID) -> list[StyleData]:
        return await self._repository.list(owner_id)

    async def get(self, style_id: UUID, *, owner_id: UUID) -> StyleData | None:
        return await self._repository.get(style_id, owner_id=owner_id)

    async def get_version(self, version_id: UUID, *, owner_id: UUID) -> StyleVersionData | None:
        return await self._repository.get_version(version_id, owner_id=owner_id)

    async def create(
        self,
        *,
        owner_id: UUID,
        name: str,
        description: str | None,
        settings: StyleSettings,
    ) -> StyleData:
        now = datetime.now(UTC)
        style = StyleData(
            id=uuid4(),
            name=name,
            description=description,
            owner_id=owner_id,
            status="active",
            created_at=now,
            updated_at=now,
        )
        manifest = self.manifest(settings)
        version = StyleVersionData(
            id=uuid4(),
            style_id=style.id,
            version=1,
            status="published",
            manifest=manifest,
            manifest_sha256=sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            settings=settings,
            validation_report={"status": "passed", "errors": [], "warnings": []},
            created_by=owner_id,
            created_at=now,
            published_at=now,
        )
        await self._repository.add(style, version)
        await self._repository.commit()
        return await self._repository.get(style.id, owner_id=owner_id) or style

    async def bootstrap(self, *, owner_id: UUID, name: str = "Инструкция Villartec A5") -> StyleData:
        now = datetime.now(UTC)
        style = StyleData(
            id=uuid4(),
            name=name,
            description=(
                "Стилизация инструкции Villartec A5: PDF и промпт образца задают визуальное "
                "направление, а документ остаётся редактируемым в редакторе."
            ),
            owner_id=owner_id,
            status="active",
            created_at=now,
            updated_at=now,
        )
        settings = self.default_settings()
        manifest = self.manifest(settings)
        version = StyleVersionData(
            id=uuid4(),
            style_id=style.id,
            version=1,
            status="published",
            manifest=manifest,
            manifest_sha256=sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            settings=settings,
            validation_report={"status": "passed", "errors": [], "warnings": []},
            created_by=owner_id,
            created_at=now,
            published_at=now,
        )
        return await self._repository.ensure_default(style, version)

    async def update_prompt(self, style: StyleData, prompt: str) -> StyleData:
        return await self.update(style, prompt=prompt)

    async def update(
        self,
        style: StyleData,
        *,
        name: str | None = None,
        description: str | None = None,
        prompt: str | None = None,
    ) -> StyleData:
        version = next((item for item in style.versions if item.status == "published"), None)
        if version is None:
            version = style.versions[0] if style.versions else None
        if version is None and prompt is not None:
            raise ValueError("Style has no version")
        if prompt is not None and version is not None:
            settings = {**version.settings, "style_prompt": prompt}
            await self._repository.update_version(self._with_settings(version, settings))
        updated_style = replace(
            style,
            name=name if name is not None else style.name,
            description=description if description is not None else style.description,
            updated_at=datetime.now(UTC),
        )
        await self._repository.update_style(updated_style)
        await self._repository.commit()
        return await self._repository.get(style.id, owner_id=style.owner_id) or style

    async def create_version(self, style: StyleData, *, owner_id: UUID) -> StyleVersionData:
        if style.status != "active":
            raise ValueError("Archived styles cannot create new versions")
        latest = style.versions[0] if style.versions else None
        now = datetime.now(UTC)
        version = StyleVersionData(
            id=uuid4(),
            style_id=style.id,
            version=latest.version + 1 if latest else 1,
            status="draft",
            manifest=dict(latest.manifest) if latest else {},
            manifest_sha256=latest.manifest_sha256 if latest else "",
            settings=dict(latest.settings) if latest else {},
            validation_report=None,
            created_by=owner_id,
            created_at=now,
            published_at=None,
        )
        await self._repository.add_version(version)
        await self._repository.update_style(replace(style, updated_at=now))
        await self._repository.commit()
        return version

    async def delete(self, style: StyleData) -> None:
        deleted = await self._repository.delete(style.id, owner_id=style.owner_id)
        if not deleted:
            raise LookupError("Style not found")
        await self._repository.commit()

    async def update_version(self, version: StyleVersionData, settings: StyleSettings) -> StyleVersionData:
        if version.status != "draft":
            raise ValueError("Only draft style versions can be edited")
        updated = self._with_settings(version, settings)
        await self._repository.update_version(updated)
        await self._repository.commit()
        return updated

    def _with_settings(self, version: StyleVersionData, settings: StyleSettings) -> StyleVersionData:
        manifest = self.manifest(settings)
        return replace(
            version,
            manifest=manifest,
            manifest_sha256=sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            settings=settings,
            validation_report=None,
        )

    async def publish(self, version: StyleVersionData) -> StyleVersionData:
        if version.status != "validating":
            raise ValueError("Validate the style version before publishing")
        await self._repository.archive_published_versions(version.style_id)
        published = replace(version, status="published", published_at=datetime.now(UTC))
        await self._repository.update_version(published)
        await self._repository.commit()
        return published

    async def validate(self, version: StyleVersionData) -> StyleVersionData:
        if version.status not in {"draft", "validating"}:
            raise ValueError("Only a draft style version can be validated")
        result = validate_style_settings(
            version.settings,
            manifest_sha256=version.manifest_sha256,
            default_theme_id=self._default_theme_id,
            default_theme_version=self._default_theme_version,
        )
        errors = list(result.errors)
        report = {
            "status": "failed" if errors else "passed",
            "errors": errors,
            "warnings": list(result.warnings),
        }
        updated = replace(version, status="validating" if not errors else "draft", validation_report=report)
        await self._repository.update_version(updated)
        await self._repository.commit()
        return updated

    async def preview(
        self,
        version: StyleVersionData,
        storage: ObjectStorage,
    ) -> dict[str, object]:
        rendered = """<!doctype html><html><head><meta charset="utf-8"><title>Style preview</title></head><body><article class="manual">
              <header class="manual-header">
                <span class="manual-header__title">Руководство по эксплуатации</span>
              </header>
              <h1 class="manual-heading--h1">Пример документа</h1>
              <p class="manual-paragraph">Так будет выглядеть основной текст документа в выбранной стилизации.</p>
              <h2 class="manual-heading--h2">Заголовок раздела</h2>
              <aside class="manual-warning"><strong class="manual-warning__title">Внимание</strong>
              <p>Пример предупреждения и компонента документа.</p></aside>
            </article></body></html>""".encode("utf-8")
        stored = await storage.put(
            key=f"style-previews/{version.id}/{version.version}.html",
            content=rendered,
            content_type="text/html",
        )
        return {"url": await storage.presign_get(key=stored.key), "expires_in": 900}

    async def attach_reference(
        self,
        version: StyleVersionData,
        *,
        filename: str,
        content: bytes,
        storage: ObjectStorage,
    ) -> dict[str, object]:
        digest = sha256(content).hexdigest()
        safe_filename = PurePosixPath(filename).name
        stored = await storage.put(
            key=f"styles/{version.style_id}/reference/{digest}-{safe_filename}",
            content=content,
            content_type="application/pdf",
        )
        settings = {
            **version.settings,
            "reference_file": {
                "key": stored.key,
                "filename": safe_filename,
                "sha256": digest,
                "size_bytes": stored.size_bytes,
            },
        }
        updated = self._with_settings(version, settings)
        await self._repository.update_version(updated)
        await self._repository.commit()
        return {
            "filename": safe_filename,
            "sha256": digest,
            "size_bytes": stored.size_bytes,
            "key": stored.key,
        }
