import re
from dataclasses import dataclass

from document_service.application.services.style_contract import DEFAULT_PAGE_MARGINS, parse_page_margins
from document_service.application.services.style_theme import SUPPORTED_RENDERER_THEMES
from document_service.domain.value_objects.document_metadata import StyleSettings


@dataclass(frozen=True, slots=True)
class StyleValidationResult:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    theme_id: str
    theme_version: str

    @property
    def passed(self) -> bool:
        return not self.errors


def validate_style_settings(
    settings: StyleSettings,
    *,
    manifest_sha256: str,
    default_theme_id: str,
    default_theme_version: str,
) -> StyleValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    page = settings.get("page", "A4, portrait")
    if not isinstance(page, str) or not re.fullmatch(
        r"\s*(A4|A5|Letter)\s*(?:,\s*(portrait|landscape))?\s*", page, re.IGNORECASE
    ):
        errors.append("Формат страницы должен быть A4, A5 или Letter с ориентацией portrait/landscape")
    if settings.get("font", "Lato") not in {"Montserrat", "Lato", "Arial", "Helvetica", "Inter"}:
        errors.append("Выбран неподдерживаемый шрифт")
    accent = settings.get("accent", "#F67828")
    if not isinstance(accent, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        errors.append("Цвет акцента должен быть в формате #RRGGBB")
    margins = parse_page_margins(settings.get("margins", DEFAULT_PAGE_MARGINS))
    if any(not 8 <= value <= 60 for value in margins.values()):
        errors.append("Поля задаются четырьмя значениями от 8 до 60 мм")
    if not settings:
        warnings.append("Параметры стилизации не заполнены; будут использованы значения темы по умолчанию")
    if not manifest_sha256:
        errors.append("Не сформирован manifest")
    theme_id = settings.get("renderer_theme_id", default_theme_id)
    theme_version = settings.get("renderer_theme_version", default_theme_version)
    theme = (theme_id, theme_version)
    if theme not in SUPPORTED_RENDERER_THEMES:
        errors.append("Выбрана неподдерживаемая тема renderer")
        theme_id, theme_version = default_theme_id, default_theme_version
    return StyleValidationResult(tuple(errors), tuple(warnings), theme_id, theme_version)
