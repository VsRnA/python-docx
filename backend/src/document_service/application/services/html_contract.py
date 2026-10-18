import re
from html.parser import HTMLParser
from urllib.parse import urlparse


_TEMPLATE_END_TAG_RE = re.compile(r"</template\s*>", flags=re.IGNORECASE)
_ORDERED_LIST_TAG_RE = re.compile(r"<ol\b[^>]*>", flags=re.IGNORECASE)
_ORDERED_LIST_TYPE_RE = re.compile(r"\s+type\s*=\s*(['\"])(.*?)\1", flags=re.IGNORECASE)
_SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", flags=re.IGNORECASE | re.DOTALL)
_VALID_ORDERED_LIST_TYPES = {"1", "a", "A", "i", "I"}


class _TemplateTagNormalizer(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=False)
        self._html = html
        self._line_offsets = [0]
        self._line_offsets.extend(index + 1 for index, char in enumerate(html) if char == "\n")
        self.removable_spans: list[tuple[int, int]] = []

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_offsets[line - 1] + column

    @staticmethod
    def _safe_attributes(attrs: list[tuple[str, str | None]]) -> bool:
        return all(
            name in {"id", "class", "lang", "title"}
            or name.startswith("data-")
            or name.startswith("aria-")
            for name, _ in attrs
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "template" or not self._safe_attributes(attrs):
            return
        raw_tag = self.get_starttag_text()
        if raw_tag:
            start = self._offset()
            self.removable_spans.append((start, start + len(raw_tag)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag != "template":
            return
        start = self._offset()
        match = _TEMPLATE_END_TAG_RE.match(self._html, start)
        if match:
            self.removable_spans.append((start, match.end()))


def normalize_html(html: str) -> str:
    parser = _TemplateTagNormalizer(html)
    parser.feed(html)
    parser.close()
    for start, end in sorted(parser.removable_spans, reverse=True):
        html = html[:start] + html[end:]
    return html


def normalize_model_html(html: str) -> str:
    html = _SCRIPT_BLOCK_RE.sub("", html)

    def normalize_ordered_list_tag(match: re.Match[str]) -> str:
        tag = match.group(0)

        def normalize_type(type_match: re.Match[str]) -> str:
            return type_match.group(0) if type_match.group(2) in _VALID_ORDERED_LIST_TYPES else ""

        return _ORDERED_LIST_TYPE_RE.sub(normalize_type, tag)

    return _ORDERED_LIST_TAG_RE.sub(normalize_ordered_list_tag, html)

FORBIDDEN_TAGS = {
    "applet",
    "base",
    "embed",
    "form",
    "iframe",
    "object",
    "script",
    "template",
}
GLOBAL_ATTRIBUTES = {
    "class",
    "data-b",
    "data-block-id",
    "data-block-type",
    "data-document-id",
    "id",
    "lang",
    "title",
    "aria-label",
}
TAG_ATTRIBUTES = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt", "width", "height"},
    "ol": {"start", "type"},
    "li": {"value"},
    "th": {"colspan", "rowspan", "colwidth", "scope"},
    "td": {"colspan", "rowspan", "colwidth"},
    "p": {"style"},
    "h1": {"style"},
    "h2": {"style"},
    "h3": {"style"},
    "h4": {"style"},
}
ALLOWED_URL_SCHEMES = {"asset", "https", "mailto", "tel"}


class HtmlContractError(ValueError):
    pass


class _ContractParser(HTMLParser):
    def __init__(self, allowed_classes: set[str] | None) -> None:
        super().__init__(convert_charrefs=True)
        self.allowed_classes = allowed_classes
        self.block_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in FORBIDDEN_TAGS or not re.fullmatch(r"[a-z][a-z0-9-]*", tag):
            raise HtmlContractError(f"Tag <{tag}> is not allowed")
        attrs_map = dict(attrs)
        for name, value in attrs_map.items():
            if name.startswith("on") and not (name == "onclick" and value == "window.print()") or name in {"formaction", "srcdoc", "xlink:href"}:
                raise HtmlContractError(f"Unsafe attribute on <{tag}>: {name}")
        style = (attrs_map.get("style") or "").strip()
        if style and re.search(r"(?:javascript:|expression\s*\(|@import|url\s*\()", style, flags=re.IGNORECASE):
            raise HtmlContractError(f"Unsafe inline style on <{tag}>")
        colwidth = (attrs_map.get("colwidth") or "").strip()
        if colwidth and not re.fullmatch(r"[1-9]\d*(,[1-9]\d*)*", colwidth):
            raise HtmlContractError(f"Invalid table column width: {colwidth}")
        start = (attrs_map.get("start") or "").strip()
        if start and not re.fullmatch(r"-?\d+", start):
            raise HtmlContractError(f"Invalid ordered-list start: {start}")
        value = (attrs_map.get("value") or "").strip()
        if value and not re.fullmatch(r"-?\d+", value):
            raise HtmlContractError(f"Invalid list item value: {value}")
        if tag == "ol":
            list_type = (attrs_map.get("type") or "").strip()
            if list_type and list_type not in {"1", "a", "A", "i", "I"}:
                raise HtmlContractError(f"Invalid ordered-list type: {list_type}")
        classes = set((attrs_map.get("class") or "").split())
        unknown_classes = classes - self.allowed_classes if self.allowed_classes is not None else set()
        if unknown_classes:
            raise HtmlContractError(f"Unknown classes: {sorted(unknown_classes)}")
        block_id = attrs_map.get("data-block-id")
        if block_id:
            block_type = attrs_map.get("data-block-type")
            if not block_type or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", block_type):
                raise HtmlContractError("Editable blocks require a safe data-block-type")
            if block_id in self.block_ids:
                raise HtmlContractError(f"Duplicate data-block-id: {block_id}")
            self.block_ids.add(block_id)
        for name in ("href", "src"):
            value = attrs_map.get(name)
            if not value:
                continue
            if name == "href" and value.startswith("#") and len(value) > 1:
                continue
            scheme = urlparse(value).scheme
            if name == "src" and scheme not in {"asset", "data", "https"}:
                raise HtmlContractError(f"Image source scheme is not allowed: {value}")
            if name == "href" and scheme not in ALLOWED_URL_SCHEMES:
                raise HtmlContractError(f"URL scheme is not allowed: {value}")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


class HtmlContractValidator:
    def __init__(self, allowed_classes: set[str] | None = None) -> None:
        self._allowed_classes = allowed_classes

    def validate(self, html: str) -> None:
        if not html.strip():
            raise HtmlContractError("HTML must not be empty")
        parser = _ContractParser(self._allowed_classes)
        parser.feed(html)
        parser.close()
