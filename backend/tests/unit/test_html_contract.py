import pytest

from document_service.application.services.html_contract import (
    HtmlContractError,
    HtmlContractValidator,
    normalize_html,
)


def test_normalize_unwraps_bare_template_container() -> None:
    html = '<template><article><p data-block-id="p1" data-block-type="paragraph">Text</p></article></template>'

    normalized = normalize_html(html)

    assert normalized == '<article><p data-block-id="p1" data-block-type="paragraph">Text</p></article>'
    HtmlContractValidator().validate(normalized)


def test_normalize_accepts_safe_template_metadata_but_not_unsafe_attributes() -> None:
    normalized = normalize_html('<template id="raw" data-slot="cover"><p>Text</p></template>')
    assert normalized == '<p>Text</p>'

    with pytest.raises(HtmlContractError, match="Tag <template> is not allowed"):
        HtmlContractValidator().validate(normalize_html('<template onclick="alert(1)"><p>Text</p></template>'))


def test_normalize_does_not_bypass_nested_unsafe_markup() -> None:

    with pytest.raises(HtmlContractError, match="Tag <script> is not allowed"):
        HtmlContractValidator().validate(normalize_html('<template><script>alert(1)</script></template>'))


def test_normalize_ignores_template_text_inside_attribute_values() -> None:
    html = '<p title="literal <template> text">Text</p>'

    assert normalize_html(html) == html


def test_contract_rejects_event_handlers() -> None:
    validator = HtmlContractValidator({"manual-paragraph"})
    with pytest.raises(HtmlContractError, match="Unsafe attribute"):
        validator.validate(
            '<p class="manual-paragraph" data-block-id="p1" data-block-type="paragraph" onclick="alert(1)">Text</p>'
        )


def test_contract_accepts_canonical_asset_reference() -> None:
    validator = HtmlContractValidator({"manual-figure"})
    validator.validate(
        '<figure class="manual-figure" data-block-id="f1" data-block-type="figure">'
        '<img src="asset://00000000-0000-0000-0000-000000000001" alt="Figure">'
        '</figure>'
    )


def test_contract_accepts_internal_toc_link_and_id() -> None:
    validator = HtmlContractValidator({"manual-toc__row", "manual-heading"})
    validator.validate(
        '<div class="manual-toc__row" data-block-id="toc-1" data-block-type="toc-row">'
        '<a href="#safety">Безопасность</a></div>'
        '<h1 id="safety" class="manual-heading" data-block-id="heading-1" data-block-type="heading">'
        'Безопасность</h1>'
    )


def test_contract_accepts_accessibility_label() -> None:
    validator = HtmlContractValidator({"manual-section"})
    validator.validate(
        '<section class="manual-section" aria-label="Safety instructions" '
        'data-block-id="section-1" data-block-type="section">Text</section>'
    )


def test_contract_accepts_openai_semantic_navigation_markup() -> None:
    validator = HtmlContractValidator()
    validator.validate(
        '<nav aria-label="Contents" class="generated-navigation">'
        '<a href="#safety">Безопасность</a>'
        '</nav>'
    )


def test_contract_accepts_tiptap_table_column_widths() -> None:
    validator = HtmlContractValidator({"manual-table"})
    validator.validate(
        '<table class="manual-table" data-block-id="table-1" data-block-type="table"><tbody><tr>'
        '<th colspan="1" rowspan="1" colwidth="180">Name</th>'
        '<td colspan="1" rowspan="1" colwidth="180,240">Value</td>'
        '</tr></tbody></table>'
    )


def test_contract_accepts_ordered_list_start() -> None:
    validator = HtmlContractValidator({"manual-list"})
    validator.validate(
        '<ol class="manual-list" start="3" data-block-id="list-1" data-block-type="ordered-list">'
        '<li>Third item</li></ol>'
    )


def test_contract_rejects_invalid_ordered_list_start() -> None:
    validator = HtmlContractValidator({"manual-list"})
    with pytest.raises(HtmlContractError, match="Invalid ordered-list start"):
        validator.validate(
            '<ol class="manual-list" start="3; color: red" data-block-id="list-1" '
            'data-block-type="ordered-list"><li>Item</li></ol>'
        )


def test_contract_rejects_invalid_table_column_widths() -> None:
    validator = HtmlContractValidator({"manual-table"})
    with pytest.raises(HtmlContractError, match="Invalid table column width"):
        validator.validate(
            '<table class="manual-table" data-block-id="table-1" data-block-type="table"><tbody><tr>'
            '<td colwidth="180; color: red">Value</td>'
            '</tr></tbody></table>'
        )


def test_contract_rejects_relative_external_resource() -> None:
    validator = HtmlContractValidator({"manual-figure"})
    with pytest.raises(HtmlContractError, match="URL scheme is not allowed"):
        validator.validate(
            '<figure class="manual-figure" data-block-id="f1" data-block-type="figure">'
            '<img src="images/figure.png" alt="Figure"></figure>'
        )
