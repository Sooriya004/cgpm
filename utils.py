from __future__ import annotations

from pathlib import Path


def normalize_prefix(value: str) -> str:
    return value.strip()


def validate_folder(folder: str) -> Path:
    path = Path(folder).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Folder does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Not a folder: {path}")
    return path


def list_matching_files(folder: Path, prefix: str) -> list[Path]:
    matches = [
        item
        for item in folder.iterdir()
        if item.is_file() and item.name.startswith(prefix)
    ]
    return sorted(matches, key=lambda item: item.name.lower())


def build_destination_name(source_name: str, source_prefix: str, target_prefix: str) -> str:
    if not source_name.startswith(source_prefix):
        raise ValueError(f"{source_name} does not start with {source_prefix}")
    return f"{target_prefix}{source_name[len(source_prefix):]}"


def names_collide(paths: list[Path]) -> bool:
    names = [path.name.lower() for path in paths]
    return len(names) != len(set(names))
