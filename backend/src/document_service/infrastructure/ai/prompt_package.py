from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PromptPackage:
    version: str
    system: str
    task: str
    schema: str
    components: str
    classes: str
    digest: str


class PromptPackageLoader:
    def __init__(self, root: Path) -> None:
        self._root = root

    def load_full_document(self, version: str) -> PromptPackage:
        directory = self._root / version
        system = (directory / "system.md").read_text(encoding="utf-8")
        task = (directory / "task-full-document.md").read_text(encoding="utf-8")
        schema = (directory / "response.schema.json").read_text(encoding="utf-8")
        components = (directory / "components.html").read_text(encoding="utf-8")
        classes = (directory / "classes.txt").read_text(encoding="utf-8")
        digest = sha256((system + task + schema + components + classes).encode()).hexdigest()
        return PromptPackage(
            version=version,
            system=system,
            task=task,
            schema=schema,
            components=components,
            classes=classes,
            digest=digest,
        )

    def load_change_set(self, version: str) -> PromptPackage:
        directory = self._root / version
        system = (directory / "system.md").read_text(encoding="utf-8")
        task = (directory / "task-change-set.md").read_text(encoding="utf-8")
        schema = (directory / "change-set.schema.json").read_text(encoding="utf-8")
        components = (directory / "components.html").read_text(encoding="utf-8")
        classes = (directory / "classes.txt").read_text(encoding="utf-8")
        digest = sha256((system + task + schema + components + classes).encode()).hexdigest()
        return PromptPackage(
            version=version,
            system=system,
            task=task,
            schema=schema,
            components=components,
            classes=classes,
            digest=digest,
        )
