import hashlib
import re
from dataclasses import dataclass

from document_service.application.ports.document_ai_editor import ChangeOperation, DocumentChangeSet

TAG_PATTERN = re.compile(r"<!--[\s\S]*?-->|<[^>]+>")
START_PATTERN = re.compile(r"<\s*([a-zA-Z][\w:-]*)\b")
END_PATTERN = re.compile(r"<\s*/\s*([a-zA-Z][\w:-]*)\s*>")
BLOCK_ID_PATTERN = re.compile(r'data-block-id\s*=\s*["\']([^"\']+)["\']')
VOID_TAGS = {"br", "hr", "img"}


@dataclass(frozen=True, slots=True)
class HtmlBlock:
    block_id: str
    start: int
    end: int
    html: str
    digest: str


class ChangeSetConflictError(ValueError):
    pass


class HtmlBlockIndex:
    def build(self, html: str) -> dict[str, HtmlBlock]:
        stack: list[tuple[str, int, str | None]] = []
        ranges: dict[str, tuple[int, int]] = {}
        for match in TAG_PATTERN.finditer(html):
            token = match.group(0)
            if token.startswith("<!--"):
                continue
            closing = END_PATTERN.fullmatch(token)
            if closing:
                tag = closing.group(1).lower()
                if not stack or stack[-1][0] != tag:
                    raise ValueError(f"Malformed HTML near closing tag </{tag}>")
                _, start, block_id = stack.pop()
                if block_id:
                    ranges[block_id] = (start, match.end())
                continue
            opening = START_PATTERN.match(token)
            if not opening:
                continue
            tag = opening.group(1).lower()
            block_match = BLOCK_ID_PATTERN.search(token)
            block_id = block_match.group(1) if block_match else None
            self_closing = token.rstrip().endswith("/>") or tag in VOID_TAGS
            if self_closing:
                if block_id:
                    ranges[block_id] = (match.start(), match.end())
            else:
                stack.append((tag, match.start(), block_id))
        if stack:
            raise ValueError("Malformed HTML: unclosed elements")

        blocks: dict[str, HtmlBlock] = {}
        for block_id, (start, end) in ranges.items():
            outer_html = html[start:end]
            blocks[block_id] = HtmlBlock(
                block_id=block_id,
                start=start,
                end=end,
                html=outer_html,
                digest=hashlib.sha256(outer_html.encode("utf-8")).hexdigest(),
            )
        return blocks


class ChangeSetApplier:
    def __init__(self) -> None:
        self._index = HtmlBlockIndex()

    def block_hashes(self, html: str) -> dict[str, str]:
        return {block_id: block.digest for block_id, block in self._index.build(html).items()}

    def apply(self, html: str, change_set: DocumentChangeSet, *, expected_revision: int) -> str:
        if change_set.base_revision != expected_revision:
            raise ChangeSetConflictError("AI change set was created for another revision")
        blocks = self._index.build(html)
        edits: list[tuple[int, int, str]] = []
        occupied: list[tuple[int, int]] = []
        for operation in change_set.operations:
            block = blocks.get(operation.block_id)
            if block is None:
                raise ChangeSetConflictError(f"Block not found: {operation.block_id}")
            if block.digest != operation.expected_hash:
                raise ChangeSetConflictError(f"Block changed: {operation.block_id}")
            self._validate_operation(operation)
            if operation.operation == "replace_block":
                edit = (block.start, block.end, operation.html or "")
            elif operation.operation == "delete_block":
                edit = (block.start, block.end, "")
            else:
                edit = (block.end, block.end, operation.html or "")
            if any(edit[0] < end and edit[1] > start for start, end in occupied):
                raise ChangeSetConflictError("AI change set contains overlapping operations")
            occupied.append((edit[0], edit[1]))
            edits.append(edit)

        result = html
        for start, end, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
            result = result[:start] + replacement + result[end:]
        return result

    @staticmethod
    def _validate_operation(operation: ChangeOperation) -> None:
        needs_html = operation.operation in {"replace_block", "insert_after"}
        if needs_html and not (operation.html or "").strip():
            raise ValueError(f"Operation {operation.operation} requires HTML")
        if operation.operation == "delete_block" and operation.html is not None:
            raise ValueError("delete_block must not contain HTML")
