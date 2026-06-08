from __future__ import annotations

import time
from collections.abc import Callable

from models import RenameItem, RenamePlan, RenameResult
from utils import build_destination_name, list_matching_files, names_collide, validate_folder


def plan_renames(folder: str, source_prefix: str, target_prefix: str) -> RenamePlan:
    folder_path = validate_folder(folder)
    source_prefix = source_prefix.strip()
    target_prefix = target_prefix.strip()

    if not source_prefix:
        raise ValueError("Source prefix is required.")
    if not target_prefix:
        raise ValueError("Target prefix is required.")

    matches = list_matching_files(folder_path, source_prefix)
    plan = RenamePlan()

    for source in matches:
        destination_name = build_destination_name(source.name, source_prefix, target_prefix)
        destination = source.with_name(destination_name)
        plan.items.append(RenameItem(source=source, destination=destination))

    if names_collide([item.destination for item in plan.items]):
        raise ValueError("Target names collide. Adjust the new prefix so each file stays unique.")

    return plan


def rename_files_with_prefix(
    folder: str,
    source_prefix: str,
    target_prefix: str,
    *,
    progress_callback: Callable[[int, int, RenameItem, float, float | None], None] | None = None,
) -> RenameResult:
    result = RenameResult()
    plan = plan_renames(folder, source_prefix, target_prefix)
    result.planned = list(plan.items)
    result.skipped = list(plan.skipped)
    start = time.perf_counter()
    total = len(plan.items)

    for index, item in enumerate(plan.items, start=1):
        if item.destination.exists() and item.destination != item.source:
            result.errors.append(f"Destination already exists: {item.destination.name}")
        else:
            try:
                item.source.rename(item.destination)
                result.renamed.append(item)
            except OSError as exc:
                result.errors.append(f"{item.source.name}: {exc}")

        elapsed = time.perf_counter() - start
        eta = None
        if index < total and index > 0:
            eta = max(0.0, (elapsed / index) * (total - index))

        if progress_callback is not None:
            progress_callback(index, total, item, elapsed, eta)

    return result
