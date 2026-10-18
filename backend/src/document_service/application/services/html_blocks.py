import re


_OPEN_TAG = re.compile(r"<(?P<tag>[A-Za-z][\w:-]*)(?P<attrs>[^<>]*?)>")
_CLASS_ATTRIBUTE = re.compile(r"\bclass\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)


def ensure_block_ids(html: str) -> str:
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        token = match.group(0)
        if re.search(r"\bdata-(?:block-id|b)\s*=", token, re.IGNORECASE):
            return token
        tag_name = match.group("tag").lower()
        class_match = _CLASS_ATTRIBUTE.search(token)
        classes = set(class_match.group(2).split()) if class_match else set()
        is_page = tag_name == "section" and "page" in classes
        if "block" not in classes and not is_page:
            return token
        counter += 1
        suffix = "/>" if token.endswith("/>") else ">"
        block_type = "page" if is_page else "block"
        return f'{token[:-len(suffix)]} data-block-id="block-{counter:04d}" data-block-type="{block_type}"{suffix}'

    return _OPEN_TAG.sub(replace, html)
