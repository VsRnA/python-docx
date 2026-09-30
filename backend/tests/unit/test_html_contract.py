import pytest

from document_service.application.services.html_contract import HtmlContractError, HtmlContractValidator


def test_contract_rejects_event_handlers() -> None:
    validator = HtmlContractValidator({"manual-paragraph"})
    with pytest.raises(HtmlContractError, match="Unknown attributes"):
        validator.validate(
            '<p class="manual-paragraph" data-block-id="p1" onclick="alert(1)">Text</p>'
        )


def test_contract_accepts_canonical_asset_reference() -> None:
    validator = HtmlContractValidator({"manual-figure"})
    validator.validate(
        '<figure class="manual-figure" data-block-id="f1">'
        '<img src="asset://00000000-0000-0000-0000-000000000001" alt="Figure">'
        '</figure>'
    )


def test_contract_accepts_internal_toc_link_and_id() -> None:
    validator = HtmlContractValidator({"manual-toc__row", "manual-heading"})
    validator.validate(
        '<div class="manual-toc__row" data-block-id="toc-1">'
        '<a href="#safety">Безопасность</a></div>'
        '<h1 id="safety" class="manual-heading" data-block-id="heading-1">'
        'Безопасность</h1>'
    )


def test_contract_accepts_tiptap_table_column_widths() -> None:
    validator = HtmlContractValidator({"manual-table"})
    validator.validate(
        '<table class="manual-table" data-block-id="table-1"><tbody><tr>'
        '<th colspan="1" rowspan="1" colwidth="180">Name</th>'
        '<td colspan="1" rowspan="1" colwidth="180,240">Value</td>'
        '</tr></tbody></table>'
    )


def test_contract_rejects_invalid_table_column_widths() -> None:
    validator = HtmlContractValidator({"manual-table"})
    with pytest.raises(HtmlContractError, match="Invalid table column width"):
        validator.validate(
            '<table class="manual-table" data-block-id="table-1"><tbody><tr>'
            '<td colwidth="180; color: red">Value</td>'
            '</tr></tbody></table>'
        )


def test_contract_rejects_relative_external_resource() -> None:
    validator = HtmlContractValidator({"manual-figure"})
    with pytest.raises(HtmlContractError, match="URL scheme is not allowed"):
        validator.validate(
            '<figure class="manual-figure" data-block-id="f1">'
            '<img src="images/figure.png" alt="Figure"></figure>'
        )
