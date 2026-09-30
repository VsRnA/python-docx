from uuid import uuid4

import pytest

from document_service.domain.entities.document import Document
from document_service.domain.value_objects.document_status import DocumentStatus


def test_document_processing_lifecycle() -> None:
    document = Document(
        title="Lawn mower",
        source_filename="manual.docx",
        source_size_bytes=1024,
        owner_id=uuid4(),
    )

    document.mark_queued()
    document.mark_processing()
    document.mark_ready()

    assert document.status is DocumentStatus.READY
    assert document.current_revision == 1


def test_document_rejects_non_docx_source() -> None:
    with pytest.raises(ValueError, match=".docx"):
        Document(
            title="Manual",
            source_filename="manual.pdf",
            source_size_bytes=1024,
            owner_id=uuid4(),
        )
