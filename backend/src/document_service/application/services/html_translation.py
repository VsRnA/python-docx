import html as html_module
import re
from dataclasses import dataclass

from document_service.application.ports.translator import TranslationSegment

TOKEN_PATTERN = re.compile(r"(<[^>]+>)")
BLOCK_ID_PATTERN = re.compile(r'data-block-id=["\']([^"\']+)["\']')


@dataclass(frozen=True, slots=True)
class ExtractedHtml:
    tokens: list[str]
    segments: list[TranslationSegment]
    token_segments: dict[int, str]


class HtmlTranslationMapper:
    def extract(self, html: str) -> ExtractedHtml:
        tokens = TOKEN_PATTERN.split(html)
        segments: list[TranslationSegment] = []
        token_segments: dict[int, str] = {}
        current_block: str | None = None
        segment_number = 0

        for index, token in enumerate(tokens):
            if token.startswith("<"):
                block_match = BLOCK_ID_PATTERN.search(token)
                if block_match:
                    current_block = block_match.group(1)
                continue
            if not token.strip():
                continue
            segment_number += 1
            segment_id = f"s{segment_number}"
            segments.append(
                TranslationSegment(
                    segment_id=segment_id,
                    text=html_module.unescape(token),
                    context=current_block,
                )
            )
            token_segments[index] = segment_id
        return ExtractedHtml(tokens=tokens, segments=segments, token_segments=token_segments)

    def merge(self, extracted: ExtractedHtml, translations: dict[str, str]) -> str:
        tokens = list(extracted.tokens)
        for token_index, segment_id in extracted.token_segments.items():
            if segment_id not in translations:
                raise ValueError(f"Missing translated segment: {segment_id}")
            tokens[token_index] = html_module.escape(translations[segment_id], quote=False)
        return "".join(tokens)
