"""Fail when inner layers import presentation or infrastructure modules."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "document_service"


def imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def main() -> int:
    violations: list[str] = []
    for layer, forbidden in (
        ("domain", ("infrastructure", "presentation", "application")),
        ("application", ("infrastructure", "presentation")),
    ):
        for path in (ROOT / layer).rglob("*.py"):
            for imported in imports(path):
                if imported.startswith("document_service." + forbidden[0]) or any(
                    imported.startswith(f"document_service.{item}.") for item in forbidden
                ):
                    violations.append(f"{path}: {imported}")
    if violations:
        print("Import boundary violations:")
        print("\n".join(violations))
        return 1
    print("Import boundaries: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
