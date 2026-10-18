from enum import StrEnum


class ProcessingProfileStatus(StrEnum):
    CREATED = "created"
    PROCESSING = "processing"
    TRANSLATING = "translating"
    COMPLETED = "completed"
    FAILED = "failed"
