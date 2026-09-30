from document_service.application.ports.document_ai_editor import ChangeOperation, DocumentChangeSet
from document_service.application.services.change_set import ChangeSetApplier, ChangeSetConflictError


def test_change_set_replaces_only_target_block() -> None:
    html = (
        '<article class="manual">'
        '<p class="manual-paragraph" data-block-id="a">Alpha</p>'
        '<p class="manual-paragraph" data-block-id="b">Beta</p>'
        '</article>'
    )
    applier = ChangeSetApplier()
    hashes = applier.block_hashes(html)
    result = applier.apply(
        html,
        DocumentChangeSet(
            base_revision=3,
            summary="Updated Alpha",
            operations=[
                ChangeOperation(
                    operation="replace_block",
                    block_id="a",
                    expected_hash=hashes["a"],
                    html='<p class="manual-paragraph" data-block-id="a">Gamma</p>',
                )
            ],
        ),
        expected_revision=3,
    )

    assert "Gamma" in result
    assert "Beta" in result


def test_change_set_rejects_stale_hash() -> None:
    html = '<p class="manual-paragraph" data-block-id="a">Alpha</p>'
    change_set = DocumentChangeSet(
        base_revision=1,
        summary="Stale edit",
        operations=[
            ChangeOperation(
                operation="delete_block",
                block_id="a",
                expected_hash="0" * 64,
            )
        ],
    )

    try:
        ChangeSetApplier().apply(html, change_set, expected_revision=1)
    except ChangeSetConflictError:
        pass
    else:
        raise AssertionError("Stale AI operation must be rejected")
