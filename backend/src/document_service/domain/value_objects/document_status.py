from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    PROCESSING_FAILED = "processing_failed"
    ARCHIVED = "archived"
    DELETED = "deleted"
