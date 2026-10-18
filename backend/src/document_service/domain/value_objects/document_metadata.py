"""Typed metadata persisted with a document and passed between adapters."""

from typing import TypedDict


class PageMargins(TypedDict):
    top_mm: float
    right_mm: float
    bottom_mm: float
    left_mm: float


class StyleSettings(TypedDict, total=False):
    page: str
    font: str
    accent: str
    margins: str | PageMargins
    renderer_theme_id: str
    renderer_theme_version: str
    


class PipelineMetadata(TypedDict, total=False):
    style_prompt_sha256: str
    source_sha256: str
    style_reference_sha256: str
    merge_notes: str
