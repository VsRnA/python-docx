from document_service.application.services.html_translation import HtmlTranslationMapper


def test_translation_mapper_preserves_markup_and_replaces_text_nodes() -> None:
    source = (
        '<section class="manual-section" data-block-id="s1">'
        '<p class="manual-paragraph" data-block-id="p1">Keep <strong>safe</strong>.</p>'
        '</section>'
    )
    mapper = HtmlTranslationMapper()
    extracted = mapper.extract(source)
    translations = {segment.segment_id: f"T:{segment.text.strip()}" for segment in extracted.segments}

    result = mapper.merge(extracted, translations)

    assert '<section class="manual-section" data-block-id="s1">' in result
    assert "<strong>" in result
    assert "T:Keep" in result
    assert "T:safe" in result
