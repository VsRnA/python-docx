from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size_bytes: int
    sha256: str
    content_type: str


class ObjectStorage(Protocol):
    async def put(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str,
    ) -> StoredObject: ...

    async def get(self, *, key: str) -> bytes: ...

    async def presign_get(self, *, key: str, expires_seconds: int = 900) -> str: ...
