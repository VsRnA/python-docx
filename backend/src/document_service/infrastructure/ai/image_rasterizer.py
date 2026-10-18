from document_service.application.services.asset_ingestor import AssetIngestor


def prepare_image_for_ai(content: bytes, mime_type: str, filename: str) -> tuple[bytes, str]:
    """Return an image format accepted by the image model.

    SVG remains the canonical document asset. It is rasterized only for the
    model request; the original asset is never overwritten.
    """
    if mime_type != "image/svg+xml":
        return content, mime_type

    AssetIngestor._validate_content(content, mime_type, filename)
    try:
        import cairosvg
    except ImportError as error:  # pragma: no cover - protected by the locked image
        raise RuntimeError("SVG image editing requires CairoSVG in the backend image") from error
    try:
        return cairosvg.svg2png(bytestring=content), "image/png"
    except Exception as error:
        raise ValueError(f"SVG image {filename} could not be rasterized for AI editing") from error
