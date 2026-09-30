from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TranslationSegment:
    segment_id: str
    text: str
    context: str | None = None


class Translator(Protocol):
    async def translate(
        self,
        segments: list[TranslationSegment],
        *,
        source_language: str,
        target_language: str,
        glossary_version: str | None = None,
    ) -> dict[str, str]: ...
