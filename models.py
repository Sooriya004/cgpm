from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RenameRule:
    folder: Path
    source_prefix: str
    target_prefix: str
    preserve_extension: bool = True


@dataclass(frozen=True)
class RenameItem:
    source: Path
    destination: Path


@dataclass
class RenamePlan:
    items: list[RenameItem] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)


@dataclass
class RenameResult:
    planned: list[RenameItem] = field(default_factory=list)
    renamed: list[RenameItem] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
