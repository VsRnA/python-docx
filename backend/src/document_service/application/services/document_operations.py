import re
def html_block_tree(html: str | None) -> dict:
    if not html:
        return {"blocks": []}
    blocks = []
    pattern = re.compile(
        r'<(?P<tag>p|h1|h2|h3|li|table|img|section|div)\b[^>]*data-(?:block-id|b)=["\'](?P<id>[^"\']+)["\'][^>]*>(?P<body>[\s\S]*?)</(?P=tag)>',
        re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        body = re.sub(r"<[^>]+>", " ", match.group("body"))
        blocks.append(
            {
                "id": match.group("id"),
                "type": match.group("tag").lower(),
                "text": re.sub(r"\s+", " ", body).strip(),
                "html": match.group(0),
                "attrs": {},
            }
        )
    return {"blocks": blocks}
