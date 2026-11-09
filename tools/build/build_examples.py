#!/usr/bin/env python3
"""Stage only requested framework modules and build examples with CPCTelera Next."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from tools.build import import_assets
    from tools.build.gen_ecs_profile import DEFAULT_PORTFOLIO, generate as generate_ecs_profile
    from tools.build.project_config import (
        BANK_PROBE,
        ProjectCapabilities,
        generate_include,
        generate_source,
        parse_capabilities,
    )
except ModuleNotFoundError:  # Direct execution: python3 tools/build/build_examples.py
    import import_assets
    from gen_ecs_profile import DEFAULT_PORTFOLIO, generate as generate_ecs_profile
    from project_config import (
        BANK_PROBE,
        ProjectCapabilities,
        generate_include,
        generate_source,
        parse_capabilities,
    )

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CPCT = Path("/config/workspace/cpctelera_next/cpctelera")
AMSDOS_NAME = re.compile(r"^[A-Z0-9][A-Z0-9_]{0,7}\.[A-Z0-9]{1,3}$")
SYMBOL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TRANSPARENCY_MODULE = "video/transparency.s"
TRANSPARENCY_REQUIRED_MODULES = {"ui/text.s", "extensions/tilemap_render_masked.s"}
EXTENDED_MEMORY_MODULE = "resources/bank.s"
ASSETS_DIR = "assets"
LOCAL_BUILD_CONFIG = Path("cfg") / "build_config.mk"


def effective_modules(
    name: str, requested_modules: object, capabilities: ProjectCapabilities
) -> list[str]:
    if not isinstance(requested_modules, list) or any(
        not isinstance(module, str) for module in requested_modules
    ):
        raise ValueError(f"{name}: modules must be a list of paths")
    if capabilities.transparency_pen is None:
        unavailable = sorted(TRANSPARENCY_REQUIRED_MODULES & set(requested_modules))
        if unavailable:
            raise ValueError(
                f"{name}: transparency must be configured for {', '.join(unavailable)}"
            )
        if TRANSPARENCY_MODULE in requested_modules:
            raise ValueError(f"{name}: {TRANSPARENCY_MODULE} requires transparency")
    if "ui/text.s" in requested_modules and capabilities.transparency_pen != 0:
        raise ValueError(f"{name}: built-in text assets require transparency pen 0")
    if EXTENDED_MEMORY_MODULE in requested_modules and not capabilities.extended_memory:
        raise ValueError(f"{name}: {EXTENDED_MEMORY_MODULE} requires extended_memory=true")

    modules = list(requested_modules)
    if capabilities.transparency_pen is not None and TRANSPARENCY_MODULE not in modules:
        modules.append(TRANSPARENCY_MODULE)
    if capabilities.extended_memory and EXTENDED_MEMORY_MODULE not in modules:
        modules.append(EXTENDED_MEMORY_MODULE)
    return modules


def _safe_example_file(example: Path, relative: str) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"unsafe example path: {relative}")
    source = (example / relative_path).resolve()
    try:
        source.relative_to(example.resolve())
    except ValueError as error:
        raise ValueError(f"unsafe example path: {relative}") from error
    if not source.is_file():
        raise ValueError(f"missing example file: {relative}")
    return source


def _write_if_changed(path: Path, content: str, encoding: str = "utf-8") -> bool:
    """Write ``content`` only when it differs, preserving mtimes for make.

    CPCTelera's Makefiles are timestamp based. Rewriting an identical header or
    configuration on every invocation would force a full rebuild, so staged
    files are compared first and left untouched when their bytes match.
    """
    data = content.encode(encoding)
    try:
        if path.read_bytes() == data:
            return False
    except FileNotFoundError:
        pass
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)
    return True


def _copy_if_changed(source: Path, destination: Path) -> bool:
    """Copy ``source`` only when its bytes differ from ``destination``."""
    data = source.read_bytes()
    try:
        if destination.read_bytes() == data:
            return False
    except FileNotFoundError:
        pass
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, destination)
    return True


def _invalidate_objects_if_profile_changed(target: Path, changed: bool) -> None:
    """Invalidate CPCTelera objects when the generated ABI include changes.

    CPCTelera's generated make rules do not track ``src/ecs_profile.inc`` as an
    explicit dependency of every framework object that includes it. Leaving
    those objects in place can therefore link a previous entity layout.
    """
    if changed:
        shutil.rmtree(target / "obj", ignore_errors=True)


def select_project_config(example: Path, default: Path) -> Path:
    """Return the CPCTelera build config used as this example's base.

    Examples that ship ``cfg/build_config.mk`` get a real, editable CPCTelera
    project configuration; the rest keep using the shared template.
    """
    local = example / LOCAL_BUILD_CONFIG
    return local if local.is_file() else default


def _config_label(config_path: Path) -> str:
    try:
        return str(config_path.resolve().relative_to(ROOT))
    except ValueError:
        return config_path.name


def stage_assets(example: Path, target: Path) -> list[str]:
    """Copy ``examples/<name>/assets`` into ``src/assets`` of the staged project.

    Every file is copied so image and audio sources stay next to the generated
    data. Files ending in ``.s`` are assembled because ``src/assets`` is a
    source subdirectory, and ``.inc`` files can be included as
    ``assets/<name>.inc``.
    """
    source_root = example / ASSETS_DIR
    if not source_root.is_dir():
        return []
    destination_root = target / "src" / ASSETS_DIR
    staged: list[str] = []
    for source in sorted(source_root.rglob("*")):
        relative = source.relative_to(source_root)
        if source.is_symlink():
            raise ValueError(f"unsafe asset symlink: {relative}")
        if not source.is_file():
            continue
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        staged.append(str(Path(ASSETS_DIR) / relative))
    return staged


def render_build_config(
    config: str,
    *,
    name: str,
    config_name: str,
    cpct_path: Path,
    targets: list[str],
    code_start: int,
) -> str:
    """Rewrite the machine and manifest dependent lines of a build config.

    Everything else in the file is preserved verbatim, so an example can add
    flags, extra tools or include paths in its own ``cfg/build_config.mk``.
    """

    def substitute(pattern: str, replacement: str, label: str) -> str:
        updated, count = re.subn(pattern, replacement, config, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(
                f"{name}: {config_name} must contain exactly one '{label}' assignment"
            )
        return updated

    config = substitute(r"^CPCT_PATH\s*:=.*$", f"CPCT_PATH      := {cpct_path}/", "CPCT_PATH :=")
    config = substitute(r"^PROJNAME\s*:=.*$", f"PROJNAME   := {name}", "PROJNAME :=")
    config = substitute(r"^TARGET\s*:=.*$", f"TARGET  := {' '.join(targets)}", "TARGET :=")
    config = substitute(
        r"^Z80CODELOC\s*:=.*$", f"Z80CODELOC := 0x{code_start:04X}", "Z80CODELOC :="
    )

    def add_source_path(match: re.Match[str]) -> str:
        line = match.group(0)
        return line if "-I$(SRCDIR)" in line else f"{line} -I$(SRCDIR)"

    config, count = re.subn(r"^Z80CCINCLUDE\s*:=.*$", add_source_path, config, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(
            f"{name}: {config_name} must contain exactly one 'Z80CCINCLUDE :=' assignment"
        )
    return config


def stage_disk_files(
    example: Path, manifest: dict, target: Path, cpct_path: Path,
    staged_paths: set[Path] | None = None,
) -> list[dict]:
    entries = manifest.get("disk_files", [])
    if not isinstance(entries, list):
        raise ValueError("disk_files must be a list")
    if entries and "dsk" not in manifest.get("media", ["cdt", "dsk"]):
        raise ValueError("disk_files require dsk media")

    staged: list[dict] = []
    names: set[str] = set()
    symbols: set[str] = set()
    include_lines = [";; Generated by tools/build/build_examples.py; do not edit."]
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("disk file entry must be an object")
        name = entry.get("name", "")
        symbol = entry.get("symbol", "")
        source_name = entry.get("source", "")
        compression = entry.get("compression", "none")
        encoding = entry.get("encoding", "raw")
        if not isinstance(name, str) or not AMSDOS_NAME.fullmatch(name):
            raise ValueError(f"invalid AMSDOS 8.3 name: {name}")
        if name in names:
            raise ValueError(f"duplicate disk filename: {name}")
        symbol_key = symbol.upper() if isinstance(symbol, str) else ""
        if (
            not isinstance(symbol, str)
            or not SYMBOL_NAME.fullmatch(symbol)
            or symbol_key in symbols
        ):
            raise ValueError(f"invalid or duplicate disk symbol: {symbol}")
        if not isinstance(source_name, str):
            raise ValueError("disk source must be a string")
        if compression not in {"none", "zx7b"}:
            raise ValueError(f"unsupported disk compression: {compression}")
        if encoding not in {"raw", "hex"}:
            raise ValueError(f"unsupported disk source encoding: {encoding}")

        source = _safe_example_file(example, source_name)
        if encoding == "hex":
            try:
                raw = bytes.fromhex(source.read_text(encoding="ascii"))
            except ValueError as error:
                raise ValueError(f"invalid hexadecimal payload: {source.name}") from error
        else:
            raw = source.read_bytes()
        if not raw:
            raise ValueError(f"empty disk payload: {source.name}")

        scratch = target / ".disk-sources" / f"{symbol}.bin"
        scratch.parent.mkdir(parents=True, exist_ok=True)
        scratch.write_bytes(raw)
        destination = target / "dsk" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if compression == "zx7b":
            compressor = cpct_path / "tools" / "zx7b" / "bin" / "zx7b"
            if not compressor.is_file():
                raise ValueError(f"missing ZX7B compressor: {compressor}")
            subprocess.run([str(compressor), str(scratch), str(destination)], check=True)
        else:
            shutil.copy2(scratch, destination)

        if staged_paths is not None:
            staged_paths.add(scratch.relative_to(target))
            staged_paths.add(destination.relative_to(target))

        prefix = f"FWK_DISK_{symbol.upper()}"
        include_lines.extend(
            [
                f"{prefix}_SIZE = 0x{destination.stat().st_size:04X}",
                f"{prefix}_UNPACKED_SIZE = 0x{len(raw):04X}",
            ]
        )
        names.add(name)
        symbols.add(symbol_key)
        staged.append(
            {
                "name": name,
                "symbol": symbol,
                "compression": compression,
                "source": source_name,
                "size": destination.stat().st_size,
                "unpacked_size": len(raw),
            }
        )

    if entries:
        _write_if_changed(
            target / "src" / "disk_files.inc",
            "\n".join(include_lines) + "\n",
            encoding="ascii",
        )
    return staged


def _validate_ecs_systems(name: str, manifest: dict, modules: list[str]) -> None:
    """Reject ECS system/component combinations that would silently misbehave."""
    if {"core/ecs_motion.s", "core/ecs_behavior.s"} & set(modules):
        ecs_config = manifest.get("ecs")
        if not isinstance(ecs_config, dict) or ecs_config.get("x_format") != "u8" or ecs_config.get("y_format") != "u8":
            raise ValueError(
                f"{name}: ECS behavior/motion systems currently require x_format=u8 and y_format=u8"
            )
        selected_components = ecs_config.get("components", [])
        if not isinstance(selected_components, list):
            raise ValueError(f"{name}: ecs components must be a list")
        if (
            "core/ecs_motion.s" in modules
            and "motion" not in selected_components
            and "behavior" not in selected_components
        ):
            raise ValueError(f"{name}: core/ecs_motion.s requires the motion component")
        if "core/ecs_behavior.s" in modules and "behavior" not in selected_components:
            raise ValueError(f"{name}: core/ecs_behavior.s requires the behavior component")
        if (
            "core/ecs_motion.s" in modules
            and "platform" in selected_components
            and "core/ecs_platform.s" not in modules
        ):
            # ecs_motion skips PLATFORM entities because ecs_platform moves
            # them; without that system they would never move at all.
            raise ValueError(
                f"{name}: the platform component needs core/ecs_platform.s "
                "when core/ecs_motion.s is selected"
            )


def stage_example(
    name: str, cpct_path: Path, example: Path | None = None, target: Path | None = None
) -> Path:
    """Stage one example, or a project folder shaped like one, into its build tree.

    ``example`` defaults to ``examples/<name>`` and ``target`` to ``build/<name>``;
    a glasnost project passes its own folder and ``<project>/build/<name>``. The
    framework (modules, profiles, templates) always comes from this repository.
    """
    example = example if example is not None else ROOT / "examples" / name
    if not example.is_dir():
        raise ValueError(f"unknown example: {name}")
    manifest = json.loads((example / "example.json").read_text(encoding="utf-8"))
    profile_path = ROOT / "framework" / "profiles" / manifest["profile"]
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    capabilities = parse_capabilities(manifest, profile["mode"])
    modules = effective_modules(name, manifest["modules"], capabilities)
    _validate_ecs_systems(name, manifest, modules)
    target = target if target is not None else ROOT / "build" / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "src").mkdir(parents=True, exist_ok=True)
    (target / "src" / "game").mkdir(parents=True, exist_ok=True)
    (target / "cfg").mkdir(parents=True, exist_ok=True)
    (target / "dsk").mkdir(parents=True, exist_ok=True)
    (target / ".disk-sources").mkdir(parents=True, exist_ok=True)
    managed_dirs = [target / "src", target / "dsk", target / ".disk-sources"]
    existing_managed = set()
    for directory in managed_dirs:
        if directory.exists():
            for path in directory.rglob("*"):
                if path.is_file():
                    existing_managed.add(path.relative_to(target))
    staged_managed = set()
    game_sources = manifest.get("game_sources", ["main.s"])
    if not game_sources or "main.s" not in game_sources:
        raise ValueError(f"{name}: game_sources must include main.s")
    for relative in game_sources:
        relative_path = Path(relative)
        source = _safe_example_file(example, relative)
        if not source.is_file() or source.suffix not in {".s", ".inc"}:
            raise ValueError(f"{name}: invalid game source {relative}")
        destination = target / "src" / "game" / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        staged_managed.add(Path("src") / "game" / relative_path)
    uses_ecs_manager = "core/ecs_manager.s" in modules
    ecs_config = manifest.get("ecs")
    if uses_ecs_manager and not isinstance(ecs_config, dict):
        raise ValueError(f"{name}: core/ecs_manager.s requires ecs configuration")
    if ecs_config is not None:
        if not uses_ecs_manager:
            raise ValueError(f"{name}: ecs configuration requires core/ecs_manager.s")
        portfolio = json.loads(DEFAULT_PORTFOLIO.read_text(encoding="utf-8"))
        generated_profile = generate_ecs_profile(manifest, portfolio, profile)
        profile_source = example / "generated" / "ecs_profile.inc"
        if (
            not profile_source.is_file()
            or profile_source.read_text(encoding="ascii") != generated_profile.include
        ):
            raise ValueError(
                f"{name}: stale ECS profile; run python3 tools/build/gen_ecs_profile.py "
                f"{_config_label(example / 'example.json')} --output "
                f"{_config_label(example / 'generated' / 'ecs_profile.inc')}"
            )
        profile_changed = _write_if_changed(
            target / "src" / "ecs_profile.inc", generated_profile.include, encoding="ascii"
        )
        _invalidate_objects_if_profile_changed(target, profile_changed)
        staged_managed.add(Path("src") / "ecs_profile.inc")
    import_assets.ensure(example, cpct_path)
    assets = stage_assets(example, target)
    for item in assets:
        staged_managed.add(Path("src") / item)
    for relative in modules:
        source = ROOT / "framework" / "src" / relative
        if not source.is_file():
            raise ValueError(f"{name}: missing module {relative}")
        destination = target / "src" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        include = source.with_suffix(".inc")
        if include.is_file():
            shutil.copy2(include, destination.with_suffix(".inc"))
            staged_managed.add(Path("src") / Path(relative).with_suffix(".inc"))
        staged_managed.add(Path("src") / relative)
    cpct_modules = manifest.get("cpct_modules", [])
    if not isinstance(cpct_modules, list):
        raise ValueError(f"{name}: cpct_modules must be a list")
    cpct_source_root = (cpct_path / "src").resolve()
    for relative in cpct_modules:
        if not isinstance(relative, str):
            raise ValueError(f"{name}: invalid CPCTelera module {relative}")
        relative_path = Path(relative)
        source = (cpct_source_root / relative_path).resolve()
        try:
            source.relative_to(cpct_source_root)
        except ValueError as error:
            raise ValueError(f"{name}: unsafe CPCTelera module {relative}") from error
        if not source.is_file() or source.suffix != ".s":
            raise ValueError(f"{name}: missing CPCTelera module {relative}")
        destination = target / "src" / "cpctelera" / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        staged_managed.add(Path("src") / "cpctelera" / relative_path)
    disk_files = stage_disk_files(example, manifest, target, cpct_path, staged_paths=staged_managed)
    config_changed = _write_if_changed(
        target / "src" / "project_config.inc", generate_include(capabilities), encoding="ascii"
    )
    config_changed |= _write_if_changed(
        target / "src" / "project_config.s", generate_source(capabilities), encoding="ascii"
    )
    # Same reason as the ECS profile, plus make 3.81 (macOS) compares whole seconds: a
    # `glasnost config` right after a build leaves the stale objects looking up to date.
    _invalidate_objects_if_profile_changed(target, config_changed)
    staged_managed.add(Path("src") / "project_config.inc")
    staged_managed.add(Path("src") / "project_config.s")
    if disk_files:
        staged_managed.add(Path("src") / "disk_files.inc")
    generated = target / "generated"
    subprocess.run(
        [
            "python3", str(ROOT / "tools" / "build" / "gen_video.py"),
            str(profile_path),
            "--out-dir", str(generated),
        ],
        check=True,
    )
    profile_name = Path(manifest["profile"]).stem
    _copy_if_changed(generated / f"{profile_name}.inc", target / "src" / "video_config.inc")
    staged_managed.add(Path("src") / "video_config.inc")
    makefile = (ROOT / "framework" / "cfg" / "Makefile.template").read_text(encoding="utf-8")
    _write_if_changed(target / "Makefile", makefile)
    config_path = select_project_config(example, ROOT / "framework" / "cfg" / "build_config.template.mk")
    config = config_path.read_text(encoding="utf-8")
    media = manifest.get("media", ["cdt", "dsk"])
    if (
        not isinstance(media, list)
        or not media
        or len(media) != len(set(media))
        or set(media) - {"cdt", "dsk"}
    ):
        raise ValueError(f"{name}: media must contain cdt and/or dsk")
    targets = ["$(CDT)" if item == "cdt" else "$(DSK)" for item in media]
    if disk_files:
        targets.append("$(DSKINC)")
    config = render_build_config(
        config,
        name=name,
        config_name=_config_label(config_path),
        cpct_path=cpct_path,
        targets=targets,
        code_start=capabilities.code_start,
    )
    (target / "cfg" / "build_config.mk").parent.mkdir(parents=True, exist_ok=True)
    _write_if_changed(target / "cfg" / "build_config.mk", config)
    _write_if_changed(
        target / "selected-modules.json",
        json.dumps(
            {
                "example": name,
                "game_sources": game_sources,
                "generated_ecs_profile": (
                    "generated/ecs_profile.inc" if ecs_config is not None else None
                ),
                "modules": modules,
                "cpct_modules": cpct_modules,
                "assets": assets,
                "build_config": str(config_path),
                "media": media,
                "disk_files": disk_files,
                "transparency": (
                    {"pen": capabilities.transparency_pen}
                    if capabilities.transparency_pen is not None
                    else None
                ),
                "extended_memory": capabilities.extended_memory,
                "code_start": capabilities.code_start,
                "cpct_path": str(cpct_path),
            },
            indent=2,
        ) + "\n",
    )
    # Remove staged files that are no longer produced, without touching obj/ so
    # CPCTelera's timestamp rules stay authoritative.
    for relative in existing_managed - staged_managed:
        (target / relative).unlink(missing_ok=True)
    for directory in managed_dirs:
        if directory.exists():
            for path in sorted(directory.rglob("*"), reverse=True):
                if path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
    return target


def _noi_value(text: str, symbol: str) -> int:
    match = re.search(rf"^DEF {re.escape(symbol)} 0x([0-9A-Fa-f]+)$", text, re.MULTILINE)
    if match is None:
        raise ValueError(f"missing linker symbol {symbol}")
    return int(match.group(1), 16)


def validate_linked_memory(target: Path, name: str, capabilities: ProjectCapabilities) -> None:
    noi = target / "obj" / f"{name}.noi"
    text = noi.read_text(encoding="ascii")
    if capabilities.extended_memory:
        init_start = _noi_value(text, "fwk_bank_init")
        init_end = _noi_value(text, "_fwk_bank_init_end")
        if init_start <= BANK_PROBE < init_end:
            raise ValueError(
                f"{name}: bank initializer 0x{init_start:04X}-0x{init_end - 1:04X} "
                f"overlaps its transient probe at 0x{BANK_PROBE:04X}"
            )


def build(
    name: str, cpct_path: Path, example: Path | None = None, target: Path | None = None
) -> None:
    if not (cpct_path / "cpctelera.lib").is_file():
        raise ValueError(f"invalid CPCT_PATH: {cpct_path}")
    example = example if example is not None else ROOT / "examples" / name
    target = stage_example(name, cpct_path, example, target)
    manifest = json.loads((example / "example.json").read_text(encoding="utf-8"))
    profile = json.loads((ROOT / "framework" / "profiles" / manifest["profile"]).read_text(encoding="utf-8"))
    capabilities = parse_capabilities(manifest, profile["mode"])
    env = os.environ.copy()
    env["CPCT_PATH"] = str(cpct_path)
    subprocess.run(["make", "--no-print-directory"], cwd=target, env=env, check=True)
    validate_linked_memory(target, name, capabilities)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("examples", nargs="*", help="example names; default: all")
    parser.add_argument("--project", type=Path, help="build a glasnost project folder instead of examples")
    parser.add_argument("--cpct-path", type=Path, default=Path(os.environ.get("CPCT_NEXT_PATH", DEFAULT_CPCT)))
    args = parser.parse_args()
    if args.project:
        folder = args.project.resolve()
        name = json.loads((folder / "example.json").read_text(encoding="utf-8"))["name"]
        print(f"== building {name} ==", flush=True)
        try:
            build(name, args.cpct_path.resolve(), folder, folder / "build")
        except (ValueError, subprocess.CalledProcessError) as error:  # a project's own mistake: no traceback
            print(f"error: {name} did not build: {error}", file=sys.stderr)
            return 1
        return 0
    names = args.examples or sorted(path.name for path in (ROOT / "examples").iterdir() if (path / "example.json").is_file())
    for name in names:
        print(f"== building {name} ==", flush=True)
        build(name, args.cpct_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
