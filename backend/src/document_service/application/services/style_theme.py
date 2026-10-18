from document_service.domain.value_objects.document_metadata import StyleSettings

SUPPORTED_RENDERER_THEMES = {
    ("villartec-manual-a4", "1.0"),
    ("villartec-manual-a5", "1.0"),
}


def resolve_renderer_theme(
    style_settings: StyleSettings | None,
    default_theme_id: str,
    default_theme_version: str,
) -> tuple[str, str]:
    settings = style_settings or {}
    theme_id = settings.get("renderer_theme_id", default_theme_id)
    theme_version = settings.get("renderer_theme_version", default_theme_version)
    if (
        isinstance(theme_id, str)
        and isinstance(theme_version, str)
        and (theme_id, theme_version) in SUPPORTED_RENDERER_THEMES
    ):
        return theme_id, theme_version
    return default_theme_id, default_theme_version
