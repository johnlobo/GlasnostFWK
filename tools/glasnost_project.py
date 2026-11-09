"""Project generator of the glasnost CLI: spec validation, template rendering, config.

Pure functions: nothing here touches the network or the toolchain, so the same spec
always renders the same bytes. `glasnost new` writes what `render_project` returns;
`glasnost config` rewrites only what this module marks as owned by glasnost.

A project folder is shaped like an example (it has an `example.json`) plus a
`glasnost.project.json`. Files owned by the user after creation: `main.s`,
`common.inc`, the `modules` / `game_sources` / `ecs` keys of `example.json`,
README, tests. Files owned by glasnost: `generated/*`, and in `example.json` the
keys `name`, `amsdos_name`, `profile`, `transparency`, `extended_memory`.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = "ecs-welcome"
TEMPLATE_DIR = ROOT / "templates" / TEMPLATE
PROJECT_FILE = "glasnost.project.json"
SCHEMA = 1
# Project format: bumped when what glasnost generates or expects of a project changes in a
# way that needs a migration (tools/glasnost_update.py). A project without the key is format 1.
FORMAT = 1

NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,23}")
TITLE_MAX = 30
# What the default sprite font can draw (src/ui/text.s).
TITLE_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !-/:>?@")
# Video profiles this template can run. experimental-160x288 needs 16-bit Y coordinates
# (u8 cannot address 288 lines) and this template uses u8, so it is not offered.
PROFILES = {"standard": "standard-160x200.json"}
MANIFEST_KEYS = {"schema", "name", "title", "profile", "extended_memory", "git"}

# Keys of example.json that `glasnost config` may rewrite.
CONFIG_OWNED = ("name", "amsdos_name", "profile", "transparency", "extended_memory")

MODULES = [
    "core/system.s",
    "core/ecs_manager.s",
    "core/ecs_behavior.s",
    "core/ecs_motion.s",
    "core/ecs_input.s",
    "extensions/behavior.s",
    "extensions/physics_platform.s",
    "core/input.s",
    "video/video.s",
    "video/sprite.s",
    "video/ecs_render.s",
    "ui/text.s",
    "resources/zx7b.s",
    "extensions/tilemap.s",
    "extensions/tilemap_render.s",
]
GAME_SOURCES = ["main.s", "common.inc", "generated/project.inc", "assets/generated/assets.inc"]
ECS_CONFIG = {"x_format": "u8", "y_format": "u8", "components": ["behavior", "input"]}

# Pen of each art character; the palette in main.s decides the colours.
ART_PENS = {".": 0, "y": 6, "r": 3, "c": 10, "w": 15, "m": 1}
SHIP_ART = [
    "...cc...",
    "..cwwc..",
    "..cwwc..",
    ".cccccc.",
    "cc.cc.cc",
    "cc.cc.cc",
    "yy....yy",
    ".y....y.",
]
DRONE_ART = [
    "..mmmm..",
    ".mmrrmm.",
    "mmrwwrmm",
    "mmrwwrmm",
    ".mmrrmm.",
    "..mmmm..",
    ".m.mm.m.",
    "m..mm..m",
]


class ProjectError(ValueError):
    """A spec or project problem; the message is a stable English identifier plus detail."""


@dataclass(frozen=True)
class Spec:
    name: str
    title: str
    profile: str = "standard"
    extended_memory: bool = False
    git: bool = True
    template: str = "ecs-welcome"

    @property
    def amsdos_name(self) -> str:
        return self.name.upper()[:8]

    @property
    def profile_file(self) -> str:
        return PROFILES[self.profile]


def normalize_title(title: str) -> str:
    if not isinstance(title, str):
        raise ProjectError("title must be text")
    value = " ".join(title.upper().split())
    if not value:
        raise ProjectError("title must not be empty")
    if len(value) > TITLE_MAX:
        raise ProjectError(f"title is longer than {TITLE_MAX} characters")
    bad = sorted(set(value) - TITLE_ALLOWED)
    if bad:
        raise ProjectError(f"title has characters the font cannot draw: {''.join(bad)!r} "
                           "(allowed: letters, digits, space and ! - / : > ? @)")
    return value


def validate(spec: Spec) -> Spec:
    if not isinstance(spec.name, str) or not NAME_RE.fullmatch(spec.name):
        raise ProjectError("name must start with a lowercase letter and have 1 to 24 "
                           "lowercase letters, digits or underscores")
    if spec.profile not in PROFILES:
        raise ProjectError(f"profile must be one of: {', '.join(PROFILES)}")
    if not isinstance(spec.extended_memory, bool) or not isinstance(spec.git, bool):
        raise ProjectError("extended_memory and git must be true or false")
    if spec.template not in ("ecs-welcome", "minimal"):
        raise ProjectError("template must be ecs-welcome or minimal")
    return Spec(spec.name, normalize_title(spec.title), spec.profile, spec.extended_memory, spec.git, spec.template)


def spec_from_manifest(data: object) -> Spec:
    """Strict reader of the `glasnost new --manifest` file."""
    if not isinstance(data, dict):
        raise ProjectError("the manifest must be a JSON object")
    unknown = sorted(set(data) - MANIFEST_KEYS)
    if unknown:
        raise ProjectError(f"unknown manifest keys: {', '.join(unknown)}")
    if data.get("schema") != SCHEMA:
        raise ProjectError(f"manifest schema must be {SCHEMA}")
    if "name" not in data:
        raise ProjectError("the manifest needs a name")
    name = data["name"]
    return validate(Spec(
        name=name,
        title=data.get("title", name.upper() if isinstance(name, str) else ""),
        profile=data.get("profile", "standard"),
        extended_memory=data.get("extended_memory", False),
        git=data.get("git", True),
        template=data.get("template", "ecs-welcome"),
    ))


def encode_mode0(left: int, right: int) -> int:
    """Two Mode 0 pixels (pens 0..15) in one video byte."""
    byte = 0
    for pen, bits in ((left, (7, 5, 3, 1)), (right, (6, 4, 2, 0))):
        for index, bit in enumerate(bits):
            if pen >> index & 1:
                byte |= 1 << bit
    return byte


def sprite_source(label: str, art: list[str]) -> str:
    """`.db` lines for an 8-pixel-wide Mode 0 sprite, with the art as comments."""
    if any(len(row) != 8 or set(row) - set(ART_PENS) for row in art):
        raise ProjectError(f"bad art for {label}")
    lines = [f";; {label}: 4 bytes x {len(art)} lines (pens: . 0, m 1, r 3, y 6, c 10, w 15)", f"{label}:"]
    for row in art:
        pens = [ART_PENS[c] for c in row]
        data = ", ".join(f"0x{encode_mode0(pens[i], pens[i + 1]):02X}" for i in range(0, 8, 2))
        lines.append(f"    .db {data}    ; {row}")
    return "\n".join(lines)


MINIMAL_MODULES = [
    "core/system.s",
    "core/input.s",
    "video/video.s",
    "ui/text.s",
    "resources/zx7b.s",
]

def example_manifest(spec: Spec) -> dict:
    modules = MINIMAL_MODULES if spec.template == "minimal" else MODULES
    game_sources = ["main.s", "common.inc", "generated/project.inc"]
    if spec.template != "minimal":
        game_sources = game_sources + ["assets/generated/assets.inc"]
    ecs_config = None if spec.template == "minimal" else copy.deepcopy(ECS_CONFIG)
    manifest = {
        "name": spec.name,
        "amsdos_name": spec.amsdos_name,
        "profile": spec.profile_file,
        "transparency": {"pen": 0},
        "extended_memory": spec.extended_memory,
        "modules": list(modules),
        "game_sources": list(game_sources),
    }
    if ecs_config is not None:
        manifest["ecs"] = ecs_config
    return manifest


def project_manifest(spec: Spec, framework: str) -> dict:
    return {"schema": SCHEMA, "template": spec.template, "format": FORMAT, "framework": framework,
            "title": spec.title}


def project_include(title: str) -> str:
    return (
        ";; Generated by glasnost from glasnost.project.json. Do not edit:\n"
        ";; change the title with `glasnost config --title`.\n"
        f'game_title: .asciz "{title}"\n'
    )


def ecs_profile_include(manifest: dict) -> str:
    """The generated ECS profile for an example.json, same generator the build checks."""
    try:
        from gen_ecs_profile import DEFAULT_PORTFOLIO, generate
    except ModuleNotFoundError:  # imported as tools.glasnost_project
        from tools.gen_ecs_profile import DEFAULT_PORTFOLIO, generate
    try:
        portfolio = json.loads(DEFAULT_PORTFOLIO.read_text(encoding="utf-8"))
        profile = json.loads((ROOT / "profiles" / manifest["profile"]).read_text(encoding="utf-8"))
        return generate(manifest, portfolio, profile).include
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ProjectError(f"the ECS profile cannot be generated: {type(error).__name__}: {error}") from error


def dump_json(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True) + "\n"


README = {
    "es": """# {title}

Proyecto creado con `glasnost new` (plantilla `ecs-welcome`, framework {framework}).
Un juego mínimo con el ECS de GlasnostFWK: una nave que se mueve con las flechas
del cursor y tres drones que patrullan.

```sh
glasnost build      # compila a build/ ({amsdos}.BIN, .CDT y .DSK)
glasnost run        # abre el .DSK en el emulador: RUN"{amsdos}
glasnost test       # comprueba el proyecto y que compila
glasnost config --title "OTRO TITULO"   # cambia título, vídeo o memoria extendida
```

Tu código está en `main.s` y `common.inc`. Lo que escribe `glasnost`
(`generated/`, y las claves `name`, `amsdos_name`, `profile`, `transparency` y
`extended_memory` de `example.json`) se regenera con `glasnost config`: no lo
edites a mano. Para usar un sistema del framework añade su componente
en `ecs.components` y su módulo en `modules` de `example.json`, y ejecuta
`glasnost config` para regenerar lo generado. Guía paso a paso (mapa y sprites importados de PNG y TMX,
animación, colisiones): `docs/first-game.md` en el SDK.
""",
    "en": """# {title}

Project created with `glasnost new` (template `ecs-welcome`, framework {framework}).
A minimal GlasnostFWK ECS game: a ship you move with the cursor keys and three
patrolling drones.

```sh
glasnost build      # builds into build/ ({amsdos}.BIN, .CDT and .DSK)
glasnost run        # opens the .DSK in the emulator: RUN"{amsdos}
glasnost test       # checks the project and that it builds
glasnost config --title "ANOTHER TITLE"   # change title, video or extended memory
```

Your code is in `main.s` and `common.inc`. What `glasnost` writes (`generated/`,
and the `name`, `amsdos_name`, `profile`, `transparency` and `extended_memory`
keys of `example.json`) is regenerated by `glasnost config`: do not edit it by
hand. To use a framework system add its component to `ecs.components` and its module
to `modules` in `example.json`, then run `glasnost config` to regenerate what is generated.
Step-by-step guide (sprites from a PNG, animation, collisions): `docs/first-game.md` in the SDK.
""",
}


def render_project(spec: Spec, framework: str, lang: str = "es") -> dict[str, bytes]:
    """Every file of a new project, as relative path -> bytes. Deterministic."""
    spec = validate(spec)
    template_dir = ROOT / "templates" / spec.template
    main = (template_dir / "main.s").read_text(encoding="utf-8")
    if "@@" in main:
        raise ProjectError("unresolved placeholder in the template")
    manifest = example_manifest(spec)
    files = {
        PROJECT_FILE: dump_json(project_manifest(spec, framework)),
        "example.json": dump_json(manifest),
        "main.s": main,
        "common.inc": (template_dir / "common.inc").read_text(encoding="utf-8"),
        "generated/project.inc": project_include(spec.title),
        ".gitignore": "build/\n",
        "README.md": README[lang].format(
            title=spec.title, name=spec.name, amsdos=spec.amsdos_name, framework=framework),
    }
    if "ecs" in manifest:
        files["generated/ecs_profile.inc"] = ecs_profile_include(manifest)
    # Copy bundled assets (PNG, TMX, palette, generated outputs).
    assets_root = template_dir / "assets"
    if assets_root.is_dir():
        for path in assets_root.rglob("*"):
            if path.is_file():
                relative = path.relative_to(assets_root).as_posix()
                files[f"assets/{relative}"] = path.read_text(encoding="utf-8") if path.suffix in (".json", ".tmx", ".inc", ".s", ".md") else path.read_bytes()
    return {path: (content.encode("ascii" if path.endswith(".inc") else "utf-8")
                   if isinstance(content, str) else content)
            for path, content in files.items()}


# ----------------------------------------------------------------- existing projects

def load_project(folder: Path) -> tuple[dict, dict]:
    """(glasnost.project.json, example.json) of a project folder, validated shallowly."""
    try:
        meta = json.loads((folder / PROJECT_FILE).read_text(encoding="utf-8"))
        example = json.loads((folder / "example.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProjectError(f"cannot read the project files: {error}") from error
    if not isinstance(meta, dict) or meta.get("schema") != SCHEMA:
        raise ProjectError(f"{PROJECT_FILE}: schema must be {SCHEMA}")
    if meta.get("template") not in ("ecs-welcome", "minimal"):
        raise ProjectError(f"{PROJECT_FILE}: unknown template {meta.get('template')!r}")
    if not isinstance(example, dict):
        raise ProjectError("example.json must be a JSON object")
    return meta, example


def project_format(meta: dict) -> int:
    """The format of a project; projects made before the key existed are format 1."""
    value = meta.get("format", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProjectError(f"{PROJECT_FILE}: format must be a whole number from 1")
    return value


def newer_format_message(found: int) -> str:
    return (f"the project is format {found} but this glasnost supports up to {FORMAT}: "
            "use a newer glasnost, or run `glasnost rollback` if you just updated")


def find_project(start: Path) -> Path | None:
    """The nearest folder at or above `start` that holds a glasnost.project.json."""
    current = start.resolve()
    for folder in (current, *current.parents):
        if (folder / PROJECT_FILE).is_file():
            return folder
    return None


def profile_key(profile_file: str) -> str:
    for key, value in PROFILES.items():
        if value == profile_file:
            return key
    raise ProjectError(f"example.json: profile {profile_file!r} is not one glasnost configures")


def owned_files(meta: dict, example: dict) -> dict[str, str]:
    """What glasnost generates for the current project state: relative path -> content."""
    title = normalize_title(meta.get("title"))
    files = {"generated/project.inc": project_include(title)}
    if example.get("ecs") is not None:
        files["generated/ecs_profile.inc"] = ecs_profile_include(example)
    return files


def check_project(folder: Path) -> list[str]:
    """Problems with a project's integrity (empty list = fine). Never writes."""
    problems: list[str] = []
    try:
        meta, example = load_project(folder)
        found = project_format(meta)
        profile_key(example.get("profile", ""))
        expected = owned_files(meta, example)
    except ProjectError as error:
        return [str(error)]
    if found > FORMAT:
        return [newer_format_message(found)]
    if example.get("name") != folder.name:
        problems.append(f"example.json name {example.get('name')!r} differs from the folder {folder.name!r}")
    amsdos = example.get("amsdos_name")
    if not isinstance(amsdos, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9_]{0,7}", amsdos):
        problems.append("example.json amsdos_name must be 1 to 8 characters A-Z, 0-9, _")
    for source in GAME_SOURCES[:2]:
        if not (folder / source).is_file():
            problems.append(f"missing {source}")
    for relative, content in expected.items():
        path = folder / relative
        try:
            current = path.read_text(encoding="ascii")
        except OSError:
            problems.append(f"missing {relative}; run glasnost config")
            continue
        if current != content:
            problems.append(f"{relative} is stale; run glasnost config")
    return problems


def apply_config(folder: Path, *, title: str | None = None, profile: str | None = None,
                 extended_memory: bool | None = None) -> dict[str, bytes]:
    """New contents of the files `glasnost config` rewrites, without writing anything.

    Raises ProjectError when the change is not valid; the caller writes the result
    only after this returns, so a bad change leaves the project untouched.
    """
    meta, example = load_project(folder)
    meta, example = copy.deepcopy(meta), copy.deepcopy(example)
    if title is not None:
        meta["title"] = normalize_title(title)
    if profile is not None:
        if profile not in PROFILES:
            raise ProjectError(f"profile must be one of: {', '.join(PROFILES)}")
        example["profile"] = PROFILES[profile]
    if extended_memory is not None:
        example["extended_memory"] = extended_memory
    profile_key(example.get("profile", ""))
    files = owned_files(meta, example)
    out = {
        PROJECT_FILE: dump_json(meta).encode("utf-8"),
        "example.json": dump_json(example).encode("utf-8"),
    }
    out.update({path: content.encode("ascii") for path, content in files.items()})
    return out
