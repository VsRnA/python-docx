from html.parser import HTMLParser
import re
from urllib.parse import urlparse

ALLOWED_TAGS = {
    "article", "section", "header", "footer", "main", "div", "span", "p",
    "h1", "h2", "h3", "h4", "ol", "ul", "li", "strong", "em", "u", "s",
    "sup", "sub", "a", "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "figure", "figcaption", "img", "br", "hr",
}
GLOBAL_ATTRIBUTES = {
    "class", "data-block-id", "data-block-type", "data-document-id", "id", "lang", "title",
}
TAG_ATTRIBUTES = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt", "width", "height"},
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
    def __init__(self, allowed_classes: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.allowed_classes = allowed_classes
        self.block_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_TAGS:
            raise HtmlContractError(f"Tag <{tag}> is not allowed")
        attrs_map = dict(attrs)
        allowed_attrs = GLOBAL_ATTRIBUTES | TAG_ATTRIBUTES.get(tag, set())
        unknown_attrs = set(attrs_map) - allowed_attrs
        if unknown_attrs:
            raise HtmlContractError(f"Unknown attributes for <{tag}>: {sorted(unknown_attrs)}")
        style = (attrs_map.get("style") or "").strip()
        if style and not re.fullmatch(
            r"text-align:\s*(left|center|right|justify);?",
            style,
            flags=re.IGNORECASE,
        ):
            raise HtmlContractError(f"Inline style is not allowed: {style}")
        colwidth = (attrs_map.get("colwidth") or "").strip()
        if colwidth and not re.fullmatch(r"[1-9]\d*(,[1-9]\d*)*", colwidth):
            raise HtmlContractError(f"Invalid table column width: {colwidth}")
        classes = set((attrs_map.get("class") or "").split())
        unknown_classes = classes - self.allowed_classes
        if unknown_classes:
            raise HtmlContractError(f"Unknown classes: {sorted(unknown_classes)}")
        block_id = attrs_map.get("data-block-id")
        if block_id:
            if block_id in self.block_ids:
                raise HtmlContractError(f"Duplicate data-block-id: {block_id}")
            self.block_ids.add(block_id)
        for name in ("href", "src"):
            value = attrs_map.get(name)
            if not value:
                continue
            if name == "href" and value.startswith("#") and len(value) > 1:
                continue
            if urlparse(value).scheme not in ALLOWED_URL_SCHEMES:
                raise HtmlContractError(f"URL scheme is not allowed: {value}")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


class HtmlContractValidator:
    def __init__(self, allowed_classes: set[str]) -> None:
        self._allowed_classes = allowed_classes

    def validate(self, html: str) -> None:
        if not html.strip():
            raise HtmlContractError("HTML must not be empty")
        parser = _ContractParser(self._allowed_classes)
        parser.feed(html)
        parser.close()
        if not parser.block_ids:
            raise HtmlContractError("Document does not contain editable blocks")
