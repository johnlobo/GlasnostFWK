"""Project update engine of the glasnost CLI: consecutive migrations, planned without writing.

A project records its `format` in glasnost.project.json (missing means 1). This SDK knows
`glasnost_project.FORMAT`. Moving a project from format N to M is a chain of one-step
migrations N -> N+1 -> ... -> M. There is no shortcut and no gap: a missing step is an error.

A migration is a pure function over the two JSON documents glasnost owns,
`glasnost.project.json` and `glasnost.manifest.json`:

    apply(meta: dict, example: dict) -> (meta, example, tasks)

It never sees main.s or common.inc, so it cannot edit your code. When a format needs a change
in your code, the migration returns it as a manual `task` (text for the update report); the
engine does not try to patch anything. After the last step the engine regenerates every file
glasnost generates (generated/*) from the migrated documents and records the framework version.

This module does not use the network and does not touch Git; planning writes nothing.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import glasnost_project as gp

Apply = Callable[[dict, dict], "tuple[dict, dict, list[str]]"]


class UpdateError(ValueError):
    """The update cannot be planned or a migration misbehaved; the message says why."""


@dataclass(frozen=True)
class Migration:
    from_format: int
    summary: str
    apply: Apply


def _manifest_v2(meta: dict, example: dict) -> tuple[dict, dict, list[str]]:
    """Format 2 changes the manifest filename; its JSON data is unchanged."""
    return meta, example, []


MIGRATIONS: dict[int, Migration] = {
    1: Migration(1, "Renombra example.json a glasnost.manifest.json", _manifest_v2),
}


@dataclass(frozen=True)
class Plan:
    folder: Path
    from_format: int
    to_format: int
    steps: tuple[Migration, ...] = ()
    files: dict[str, bytes] = field(default_factory=dict)   # everything glasnost would write
    changed: tuple[str, ...] = ()                            # those that differ from disk
    tasks: tuple[str, ...] = ()                              # manual work for the user
    removed: tuple[str, ...] = ()                            # owned files retired by migration

    @property
    def empty(self) -> bool:
        return self.from_format == self.to_format


def _check_documents(step: Migration, meta: object, example: object, tasks: object, name: str) -> None:
    where = f"migration from format {step.from_format}"
    if not isinstance(meta, dict) or not isinstance(example, dict):
        raise UpdateError(f"{where} must return the two documents as objects")
    if not isinstance(tasks, list) or any(not isinstance(task, str) or not task.strip() for task in tasks):
        raise UpdateError(f"{where} must return its manual tasks as a list of non-empty text")
    if example.get("name") != name:
        raise UpdateError(f"{where} must not rename the project (name is tied to the folder)")
    if "format" in meta and meta["format"] != step.from_format:
        raise UpdateError(f"{where} must not set the format itself; the engine does")


def plan_update(
    folder: Path,
    framework: str,
    migrations: dict[int, Migration] | None = None,
    target: int | None = None,
) -> Plan:
    """What updating `folder` to `target` (default: this SDK's format) would do. Writes nothing."""
    migrations = MIGRATIONS if migrations is None else migrations
    target = gp.FORMAT if target is None else target
    try:
        meta, example = gp.load_project(folder)
        current = gp.project_format(meta)
    except gp.ProjectError as error:
        raise UpdateError(str(error)) from error
    if current > target:
        raise UpdateError(
            f"the project is format {current}, newer than the {target} this glasnost supports; "
            "update glasnost instead (a project is never downgraded)")
    if current == target:
        return Plan(folder, current, target)

    steps: list[Migration] = []
    for number in range(current, target):
        step = migrations.get(number)
        if step is None:
            raise UpdateError(f"no migration from format {number} to {number + 1}: "
                              "migrations are consecutive and none may be skipped")
        if step.from_format != number:
            raise UpdateError(f"the migration registered for format {number} says it starts at "
                              f"{step.from_format}")
        steps.append(step)

    source_manifest = gp.manifest_path(folder)
    original_example = copy.deepcopy(example)
    name = example.get("name")
    meta, example = copy.deepcopy(meta), copy.deepcopy(example)
    tasks: list[str] = []
    for step in steps:
        try:
            meta, example, step_tasks = step.apply(meta, example)  # our private copies
        except UpdateError:
            raise
        except Exception as error:  # a migration bug must not leave a half-planned update
            raise UpdateError(f"migration from format {step.from_format} failed: "
                              f"{type(error).__name__}: {error}") from error
        _check_documents(step, meta, example, step_tasks, name)
        meta["format"] = step.from_format + 1
        tasks.extend(f"format {step.from_format} to {step.from_format + 1}: {task.strip()}"
                     for task in step_tasks)
    meta["framework"] = framework

    try:
        generated = gp.owned_files(meta, example)
    except gp.ProjectError as error:
        raise UpdateError(f"the migrated project is not valid: {error}") from error
    destination = gp.MANIFEST_FILE if target >= 2 else source_manifest.name
    files = {
        gp.PROJECT_FILE: gp.dump_json(meta).encode("utf-8"),
        destination: (source_manifest.read_bytes() if example == original_example
                      else gp.dump_json(example).encode("utf-8")),
        **{path: text.encode("ascii") for path, text in generated.items()},
    }
    removed = (source_manifest.name,) if source_manifest.name != destination else ()
    changed = tuple(sorted({
        path for path, content in files.items()
        if not (folder / path).is_file() or (folder / path).read_bytes() != content
    } | set(removed)))
    return Plan(folder, current, target, tuple(steps), files, changed, tuple(tasks), removed)
