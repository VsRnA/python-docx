"""Canonical style settings shared by application use cases and adapters."""

from __future__ import annotations

import re

from document_service.domain.value_objects.document_metadata import PageMargins

STYLE_CONTRACT_VERSION = 1


DEFAULT_PAGE_MARGINS: PageMargins = {
    "top_mm": 24.0,
    "right_mm": 13.0,
    "bottom_mm": 18.0,
    "left_mm": 13.0,
}


def parse_page_margins(value: object) -> PageMargins:
    if isinstance(value, dict):
        keys = ("top_mm", "right_mm", "bottom_mm", "left_mm")
        if all(isinstance(value.get(key), int | float) for key in keys):
            parsed = {key: float(value[key]) for key in keys}
        else:
            parsed = DEFAULT_PAGE_MARGINS.copy()
    elif isinstance(value, str):
        numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", value)]
        if len(numbers) == 3:
            parsed = dict(zip(("top_mm", "right_mm", "bottom_mm"), numbers, strict=True))
            parsed["left_mm"] = parsed["right_mm"]
        elif len(numbers) == 4:
            parsed = dict(zip(("top_mm", "right_mm", "bottom_mm", "left_mm"), numbers, strict=True))
        else:
            parsed = DEFAULT_PAGE_MARGINS.copy()
    else:
        parsed = DEFAULT_PAGE_MARGINS.copy()
    if not all(8 <= value <= 60 for value in parsed.values()):
        return DEFAULT_PAGE_MARGINS.copy()
    return parsed


def margins_as_css(value: object) -> str:
    margins = parse_page_margins(value)
    return " ".join(f"{margins[key]:g}mm" for key in ("top_mm", "right_mm", "bottom_mm", "left_mm"))
