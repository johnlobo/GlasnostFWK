#!/usr/bin/env python3
"""glasnost: single interface of the GlasnostFWK SDK (messages in es/en).

Commands: doctor, install-toolchain, build, test, run, path, version.

The CPCTelera Next toolchain is managed: `install-toolchain` fetches the commit
pinned in toolchain.lock.json and builds it under
`.toolchain/cpctelera-next/<commit>/` (outside Git, no sudo). `CPCT_NEXT_PATH`
overrides it for development. Nothing here touches the network except
`install-toolchain` (and `doctor --network`).
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import glasnost_project as gp  # noqa: E402
import glasnost_update as gu  # noqa: E402
from glasnost_i18n import LANGS, pick_language, say  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LOCKFILE = "toolchain.lock.json"
COMPLETE_MARKER = ".glasnost-complete"
MIN_PYTHON = (3, 10)
BOOST_HEADER_CANDIDATES = (
    Path("/usr/include/boost/version.hpp"),
    Path("/opt/homebrew/include/boost/version.hpp"),
    Path("/usr/local/include/boost/version.hpp"),
    Path("/opt/local/include/boost/version.hpp"),
)
BOOST_HEADER = next((p for p in BOOST_HEADER_CANDIDATES if p.is_file()),
                    BOOST_HEADER_CANDIDATES[0])
BUILD_TOOLS = ("git", "make", "gcc", "g++", "bison", "flex")

# Built by install-toolchain, in this order (same list as the release workflow).
# Paths are relative to the `cpctelera/` directory of the checkout; "." is the library.
MAKE_STEPS = (
    "tools/sdcc-4.5.0",
    "tools/hex2bin-2.0",
    "tools/iDSK-0.13",
    "tools/2cdt",
    "tools/cpc2cdt",
    "tools/img2cpc",
    ".",
    "tools/zx7b",
)
# What a usable toolchain must contain.
REQUIRED_FILES = (
    "cpctelera.lib",
    "tools/sdcc-4.5.0/bin/sdcc",
    "tools/hex2bin-2.0/bin/hex2bin",
    "tools/iDSK-0.13/bin/iDSK",
    "tools/2cdt/bin/2cdt",
    "tools/cpc2cdt/bin/cpc2cdt",
    "tools/img2cpc/bin/img2cpc",
    "tools/zx7b/bin/zx7b",
)

# Pseudo-commands of the install plan that are not subprocesses.
FETCH, VERIFY, MARK = "<fetch>", "<verify>", "<mark>"

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class CliError(Exception):
    """A failure whose message is already translated and ready to print."""


@dataclass(frozen=True)
class Lock:
    url: str
    rev: str


@dataclass(frozen=True)
class Toolchain:
    path: Path          # the cpctelera/ directory (what CPCT_NEXT_PATH points to)
    source: str         # "env" or "managed"
    rev: str | None


def load_lock(root: Path, lang: str) -> Lock:
    try:
        data = json.loads((root / LOCKFILE).read_text(encoding="utf-8"))
        if data.get("schema") != 1:
            raise ValueError("schema must be 1")
        entry = data["cpctelera_next"]
        url, rev = entry["url"], entry["rev"]
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("url must be an https URL")
        if not isinstance(rev, str) or not re.fullmatch(r"[0-9a-f]{40}", rev):
            raise ValueError("rev must be a full 40-character commit hash")
    except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
        raise CliError(say(lang, "cmd.lockfile_bad", reason=f"{type(error).__name__}: {error}")) from error
    override = os.environ.get("GLASNOST_CPCTELERA_URL")
    if override is not None:
        # same rule as the lockfile, plus file:// for local mirrors; never an option or a
        # git transport helper such as ext::
        if not re.fullmatch(r"(https://|file:///)[^\s]+", override):
            raise CliError(say(lang, "cmd.lockfile_bad", reason="GLASNOST_CPCTELERA_URL must be https:// or file:///"))
        url = override
    return Lock(url=url, rev=rev)


def toolchain_dir(root: Path) -> Path:
    base = os.environ.get("GLASNOST_TOOLCHAIN_DIR")
    return Path(base).resolve() if base else root / ".toolchain"


def managed_root(root: Path, lock: Lock) -> Path:
    """Git checkout of the pinned commit; cpctelera/ lives inside it."""
    return toolchain_dir(root) / "cpctelera-next" / lock.rev


def missing_files(cpct: Path) -> list[str]:
    absent = []
    for relative in REQUIRED_FILES:
        candidate = cpct / relative
        if not candidate.is_file() or candidate.stat().st_size == 0:
            absent.append(relative)
        elif relative != "cpctelera.lib" and not os.access(candidate, os.X_OK):
            absent.append(relative)
    return absent


def resolve_toolchain(root: Path, lock: Lock, lang: str) -> Toolchain:
    """CPCT_NEXT_PATH wins (development); otherwise the managed install."""
    override = os.environ.get("CPCT_NEXT_PATH")
    if override:
        cpct, source, rev = Path(override).resolve(), "env", None
    else:
        checkout = managed_root(root, lock)
        cpct, source, rev = checkout / "cpctelera", "managed", lock.rev
        if not (checkout / COMPLETE_MARKER).is_file():
            raise CliError(say(lang, "toolchain.not_installed"))
    absent = missing_files(cpct)
    if absent:
        raise CliError(say(lang, "toolchain.invalid", path=cpct, missing=", ".join(absent)))
    return Toolchain(path=cpct, source=source, rev=rev)


def default_runner(command: Sequence[str], **kwargs) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(list(command), text=True, **kwargs)


# -------------------------------------------------------- install-deps

PLATFORM_PACKAGES = {
    "darwin": {"brew": ["python3", "git", "make", "bison", "flex", "boost"]},
    "debian": {"apt": ["python3", "git", "build-essential", "bison", "flex", "libboost-dev"]},
    "fedora": {"dnf": ["python3", "git", "make", "gcc", "gcc-c++", "bison", "flex", "boost-devel"]},
    "arch": {"pacman": ["python", "git", "base-devel", "bison", "flex", "boost"]},
    "suse": {"zypper": ["python3", "git", "make", "gcc", "gcc-c++", "bison", "flex", "boost-devel"]},
}


def detect_platform() -> tuple[str, str] | None:
    """Return (platform_key, manager) or None if unsupported."""
    if sys.platform == "darwin":
        return ("darwin", "brew")
    if sys.platform.startswith("linux"):
        for manager in ("apt", "dnf", "pacman", "zypper"):
            if shutil.which(manager):
                if manager == "apt":
                    return ("debian", "apt")
                if manager == "dnf":
                    return ("fedora", "dnf")
                if manager == "pacman":
                    return ("arch", "pacman")
                if manager == "zypper":
                    return ("suse", "zypper")
    return None


def missing_dependencies() -> list[str]:
    absent = [tool for tool in BUILD_TOOLS if not shutil.which(tool)]
    if not BOOST_HEADER.is_file():
        absent.append("libboost-dev")
    return absent


def cmd_install_deps(args, root: Path, lang: str, runner: Runner) -> int:
    platform = detect_platform()
    if platform is None:
        print(say(lang, "install_deps.no_manager", platform=sys.platform,
                  packages=", ".join(BUILD_TOOLS) + ", libboost-dev"))
        return 1
    platform_key, manager = platform
    packages = PLATFORM_PACKAGES[platform_key][manager]
    print(say(lang, "install_deps.platform", platform=sys.platform, manager=manager))
    if not missing_dependencies():
        print(say(lang, "install_deps.already"))
        return 0
    print(say(lang, "install_deps.running", packages=", ".join(packages)))
    if not args.yes:
        try:
            answer = input(say(lang, "install_deps.confirm", packages=", ".join(packages)) + " ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("s", "y", "si", "sí", "yes"):
            print(say(lang, "install_deps.cancelled"))
            return 1
    if manager == "brew":
        command = ["brew", "install", *packages]
    elif manager == "apt":
        command = ["sudo", "apt", "install", "-y", *packages]
    elif manager == "dnf":
        command = ["sudo", "dnf", "install", "-y", *packages]
    elif manager == "pacman":
        command = ["sudo", "pacman", "-S", "--noconfirm", *packages]
    elif manager == "zypper":
        command = ["sudo", "zypper", "install", "-y", *packages]
    else:
        print(say(lang, "install_deps.no_manager", platform=sys.platform, packages=", ".join(packages)))
        return 1
    result = runner(command, check=False)
    if result.returncode != 0:
        raise CliError(say(lang, "install_deps.failed", platform=sys.platform))
    print(say(lang, "install_deps.done"))
    return 0


# ----------------------------------------------------------------- doctor

def sdk_version(root: Path, runner: Runner) -> str:
    try:
        result = runner(["git", "describe", "--tags", "--always"], cwd=root,
                        capture_output=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except OSError:
        pass
    return "dev"


def doctor_checks(root: Path, lock: Lock, lang: str, network: bool, runner: Runner) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    python_ok = sys.version_info[:2] >= MIN_PYTHON
    checks.append(("python3", python_ok, sys.version.split()[0]
                   + ("" if python_ok else f" < {MIN_PYTHON[0]}.{MIN_PYTHON[1]}")))
    for tool in BUILD_TOOLS:
        found = shutil.which(tool)
        checks.append((tool, bool(found),
                       say(lang, "doctor.tool_found", path=found) if found else say(lang, "doctor.tool_missing")))
    boost = BOOST_HEADER.is_file()
    checks.append((say(lang, "doctor.lib_boost"), boost,
                   str(BOOST_HEADER) if boost else say(lang, "doctor.lib_boost_missing")))
    try:
        toolchain = resolve_toolchain(root, lock, lang)
        detail = (say(lang, "doctor.toolchain_env", path=toolchain.path) if toolchain.source == "env"
                  else say(lang, "doctor.toolchain_managed", rev=lock.rev[:12], path=toolchain.path))
        checks.append(("CPCTelera Next", True, detail))
    except CliError as error:
        checks.append(("CPCTelera Next", False, str(error)))
    if network:
        try:
            reachable = runner(["git", "ls-remote", lock.url, "HEAD"], capture_output=True,
                               timeout=15, check=False).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            reachable = False
        checks.append(("network", reachable,
                       say(lang, "doctor.network_ok" if reachable else "doctor.network", url=lock.url)))
    return checks


def cmd_doctor(args, root: Path, lang: str, runner: Runner) -> int:
    lock = load_lock(root, lang)
    print(say(lang, "doctor.title", version=sdk_version(root, runner)))
    failed = 0
    for name, ok, detail in doctor_checks(root, lock, lang, args.network, runner):
        print(say(lang, "doctor.ok" if ok else "doctor.missing", name=name, detail=detail))
        failed += 0 if ok else 1
    print(say(lang, "doctor.summary_fail", count=failed) if failed else say(lang, "doctor.summary_ok"))
    return 1 if failed else 0


# -------------------------------------------------------- install-toolchain

def install_plan(root: Path, lock: Lock, lang: str, jobs: int) -> list[tuple[str, list[str]]]:
    """Ordered (label, command) steps; pseudo-commands are FETCH, VERIFY and MARK."""
    checkout = managed_root(root, lock)
    cpct = checkout / "cpctelera"
    steps: list[tuple[str, list[str]]] = [
        (say(lang, "toolchain.step_fetch", url=lock.url, path=checkout), [FETCH]),
    ]
    for relative in MAKE_STEPS:
        target = cpct if relative == "." else cpct / relative
        label = "cpctelera.lib" if relative == "." else relative
        steps.append((say(lang, "toolchain.step_make", target=label),
                      ["make", "-C", str(target), f"-j{jobs}"]))
    steps.append((say(lang, "toolchain.step_verify"), [VERIFY]))
    steps.append((say(lang, "toolchain.step_publish", path=checkout), [MARK]))
    return steps


def run_checked(runner: Runner, command: Sequence[str], label: str, lang: str, checkout: Path) -> None:
    if runner(command, check=False).returncode != 0:
        raise CliError(say(lang, "toolchain.failed", step=label, path=checkout))


def fetch_pinned(runner: Runner, lock: Lock, checkout: Path, label: str, lang: str) -> None:
    """Same fetch the release workflow does: shallow, exactly the pinned commit."""
    checkout.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(checkout)]
    if not (checkout / ".git").exists():
        run_checked(runner, ["git", "init", "-q", str(checkout)], label, lang, checkout)
    remotes = runner([*git, "remote"], capture_output=True, check=False).stdout.split()
    verb = "set-url" if "origin" in remotes else "add"
    run_checked(runner, [*git, "remote", verb, "origin", lock.url], label, lang, checkout)
    run_checked(runner, [*git, "fetch", "-q", "--depth=1", "origin", lock.rev], label, lang, checkout)
    run_checked(runner, [*git, "checkout", "-q", "-f", "--detach", "FETCH_HEAD"], label, lang, checkout)
    head = runner([*git, "rev-parse", "HEAD"], capture_output=True, check=False).stdout.strip()
    if head != lock.rev:
        raise CliError(say(lang, "toolchain.rev_mismatch", got=head, want=lock.rev))


def cmd_install(args, root: Path, lang: str, runner: Runner) -> int:
    lock = load_lock(root, lang)
    checkout = managed_root(root, lock)
    jobs = max(1, min(os.cpu_count() or 1, 4))
    plan = install_plan(root, lock, lang, jobs)

    print(say(lang, "toolchain.plan_title", rev=lock.rev))
    if args.dry_run:
        for number, (label, _command) in enumerate(plan, 1):
            print(say(lang, "toolchain.plan_step", n=number, total=len(plan), text=label))
        print(say(lang, "toolchain.dry_run"))
        return 0

    complete = (checkout / COMPLETE_MARKER).is_file() and not missing_files(checkout / "cpctelera")
    if complete and not args.force:
        print(say(lang, "toolchain.already", rev=lock.rev[:12], path=checkout))
        return 0

    absent = [tool for tool in BUILD_TOOLS if not shutil.which(tool)]
    if not BOOST_HEADER.is_file():
        absent.append("libboost-dev")
    if absent:
        raise CliError(say(lang, "toolchain.missing_prereq", names=", ".join(absent)))

    with install_lock(checkout, lang):
        return run_install(args, lock, checkout, plan, lang, runner)


@contextlib.contextmanager
def install_lock(checkout: Path, lang: str):
    """One install per commit at a time: a second one would corrupt the first."""
    checkout.parent.mkdir(parents=True, exist_ok=True)
    with open(checkout.parent / f".{checkout.name}.lock", "w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise CliError(say(lang, "toolchain.locked", path=checkout)) from error
        yield


def run_install(args, lock: Lock, checkout: Path, plan, lang: str, runner: Runner) -> int:
    if args.force and checkout.exists():
        shutil.rmtree(checkout)
    # a retry starts incomplete: the marker comes back only after the last step
    (checkout / COMPLETE_MARKER).unlink(missing_ok=True)
    for number, (label, command) in enumerate(plan, 1):
        print(say(lang, "toolchain.plan_step", n=number, total=len(plan), text=label), flush=True)
        if command == [FETCH]:
            fetch_pinned(runner, lock, checkout, label, lang)
        elif command == [VERIFY]:
            absent_files = missing_files(checkout / "cpctelera")
            if absent_files:
                raise CliError(say(lang, "toolchain.invalid", path=checkout / "cpctelera",
                                   missing=", ".join(absent_files)))
        elif command == [MARK]:
            (checkout / COMPLETE_MARKER).write_text(lock.rev + "\n", encoding="utf-8")
        else:
            run_checked(runner, command, label, lang, checkout)
    print(say(lang, "toolchain.done", rev=lock.rev[:12], path=checkout))
    return 0


# ------------------------------------------- toolchains: list and clean

REV_DIR = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class InstalledToolchain:
    rev: str
    path: Path
    complete: bool
    size: int
    pinned: bool


def tree_size(path: Path) -> int:
    total = 0
    for base, _dirs, files in os.walk(path):  # os.walk does not follow directory symlinks
        for name in files:
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(base, name)).st_size
    return total


def installed_toolchains(root: Path, lock: Lock) -> list[InstalledToolchain]:
    """Real directories named like a commit under cpctelera-next/; anything else is ignored."""
    parent = toolchain_dir(root) / "cpctelera-next"
    found = []
    if parent.is_dir() and not parent.is_symlink():
        for entry in sorted(parent.iterdir()):
            if not REV_DIR.fullmatch(entry.name) or entry.is_symlink() or not entry.is_dir():
                continue
            complete = (entry / COMPLETE_MARKER).is_file() and not missing_files(entry / "cpctelera")
            found.append(InstalledToolchain(entry.name, entry, complete, tree_size(entry), entry.name == lock.rev))
    return found


def human_size(size: int) -> str:
    return f"{size / 1_000_000:.0f} MB" if size >= 1_000_000 else f"{size / 1000:.0f} kB"


def cmd_toolchains(args, root: Path, lang: str, runner: Runner) -> int:
    lock = load_lock(root, lang)
    found = installed_toolchains(root, lock)
    if not found:
        print(say(lang, "tc.none", path=toolchain_dir(root)))
        return 0
    for item in found:
        state = say(lang, "tc.complete" if item.complete else "tc.partial")
        pinned = say(lang, "tc.pinned") if item.pinned else ""
        print(say(lang, "tc.row", rev=item.rev[:12], state=state, size=human_size(item.size), pinned=pinned).rstrip())
    return 0


def cmd_clean(args, root: Path, lang: str, runner: Runner) -> int:
    """Remove every installed toolchain except the one the lockfile pins.

    Without --yes it only lists. A shared GLASNOST_TOOLCHAIN_DIR may hold toolchains
    that another SDK version pins: --keep REV protects those.
    """
    lock = load_lock(root, lang)
    keep = {lock.rev, *(rev.lower() for rev in args.keep)}
    for rev in args.keep:
        if not REV_DIR.fullmatch(rev.lower()):
            raise CliError(say(lang, "tc.bad_keep", rev=rev))
    doomed = [item for item in installed_toolchains(root, lock) if item.rev not in keep]
    if not doomed:
        print(say(lang, "tc.nothing_to_clean"))
        return 0
    for item in doomed:
        print(say(lang, "tc.will_remove", rev=item.rev[:12], size=human_size(item.size), path=item.path))
    if os.environ.get("GLASNOST_TOOLCHAIN_DIR"):
        print(say(lang, "tc.shared_warning", path=toolchain_dir(root)))
    if not args.yes:
        print(say(lang, "tc.clean_preview"))
        return 0
    freed = 0
    for item in doomed:
        with install_lock(item.path, lang):  # never race an install of the same commit
            shutil.rmtree(item.path)
        (item.path.parent / f".{item.rev}.lock").unlink(missing_ok=True)
        freed += item.size
    print(say(lang, "tc.cleaned", count=len(doomed), size=human_size(freed)))
    return 0


# ------------------------------------------------------ install-cli / uninstall

def cli_link(args) -> Path:
    base = args.prefix or os.environ.get("GLASNOST_BIN_DIR") or str(Path.home() / ".local" / "bin")
    return Path(base).expanduser().resolve() / "glasnost"


def cmd_install_cli(args, root: Path, lang: str, runner: Runner) -> int:
    link, source = cli_link(args), (root / "bin" / "glasnost").resolve()
    if args.dry_run:
        print(say(lang, "cli.plan", link=link, source=source))
        return 0
    if link.is_symlink() and link.resolve() == source:
        print(say(lang, "cli.already", link=link))
    else:
        if link.exists() or link.is_symlink():
            if not args.force:
                raise CliError(say(lang, "cli.exists", link=link))
            link.unlink()
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(source)
        print(say(lang, "cli.installed", link=link, source=source))
    if str(link.parent) not in os.environ.get("PATH", "").split(os.pathsep):
        print(say(lang, "cli.path_hint", dir=link.parent))
    return 0


def cmd_uninstall_cli(args, root: Path, lang: str, runner: Runner) -> int:
    """Remove only the symlink that points at this SDK; nothing else, ever."""
    link, source = cli_link(args), (root / "bin" / "glasnost").resolve()
    if not link.is_symlink():
        if link.exists():
            raise CliError(say(lang, "cli.not_ours", link=link))
        print(say(lang, "cli.absent", link=link))
        return 0
    if link.resolve() != source:
        raise CliError(say(lang, "cli.not_ours", link=link))
    link.unlink()
    print(say(lang, "cli.removed", link=link))
    return 0


# ------------------------------------------------------- build / test / run

def example_names(root: Path) -> list[str]:
    return sorted(p.name for p in (root / "examples").iterdir() if (p / "example.json").is_file())


def check_examples(root: Path, names: Sequence[str], lang: str) -> None:
    known = example_names(root)
    for name in names:
        if name not in known:
            raise CliError(say(lang, "cmd.unknown_example", name=name, names=", ".join(known)))


def sdk_env(toolchain: Toolchain) -> dict[str, str]:
    return dict(os.environ, CPCT_NEXT_PATH=str(toolchain.path))


def current_project(args, lang: str | None = None) -> Path | None:
    """The project the command runs in: --project, else the nearest folder above the cwd."""
    explicit = getattr(args, "project", None)
    if explicit:  # an explicit folder must be a project: never fall back to the framework
        folder = Path(explicit).resolve()
        if not (folder / gp.PROJECT_FILE).is_file():
            raise CliError(say(lang or lang_of(args), "proj.not_a_project", path=folder))
        return folder
    return gp.find_project(Path.cwd())


def lang_of(args) -> str:
    return getattr(args, "lang_resolved", "es")


def require_project_ok(folder: Path, lang: str) -> None:
    problems = gp.check_project(folder)
    if problems:
        raise CliError(say(lang, "proj.check_failed", path=folder) + "\n" + "\n".join(f"  - {p}" for p in problems))


def build_project(folder: Path, toolchain: Toolchain, root: Path, lang: str, runner: Runner) -> int:
    require_project_ok(folder, lang)
    return runner([sys.executable, "tools/build_examples.py", "--project", str(folder)],
                  cwd=root, env=sdk_env(toolchain), check=False).returncode


def cmd_build(args, root: Path, lang: str, runner: Runner) -> int:
    toolchain = resolve_toolchain(root, load_lock(root, lang), lang)
    folder = current_project(args)
    if folder:
        if args.examples:
            raise CliError(say(lang, "proj.no_examples", path=folder))
        return build_project(folder, toolchain, root, lang, runner)
    check_examples(root, args.examples, lang)
    env = sdk_env(toolchain)
    python = sys.executable
    generated = runner(["make", "--no-print-directory", "generate", f"PYTHON={python}"],
                       cwd=root, env=env, check=False)
    if generated.returncode != 0:
        return generated.returncode
    return runner([python, "tools/build_examples.py", *args.examples],
                  cwd=root, env=env, check=False).returncode


def cmd_test(args, root: Path, lang: str, runner: Runner) -> int:
    toolchain = resolve_toolchain(root, load_lock(root, lang), lang)
    folder = current_project(args)
    if folder:  # a project: its integrity, then that it builds
        code = build_project(folder, toolchain, root, lang, runner)
        if code == 0:
            print(say(lang, "proj.test_ok", name=folder.name))
        return code
    return runner(["make", "test", f"PYTHON={sys.executable}"],
                  cwd=root, env=sdk_env(toolchain), check=False).returncode


def cmd_run(args, root: Path, lang: str, runner: Runner) -> int:
    toolchain = resolve_toolchain(root, load_lock(root, lang), lang)
    folder = current_project(args)
    tokens = list(args.rest)  # [example] [-- emulator options]
    example = tokens.pop(0) if tokens and not tokens[0].startswith("-") else None
    extra = tokens[1:] if tokens[:1] == ["--"] else tokens
    if folder:
        if example:
            raise CliError(say(lang, "proj.no_examples", path=folder))
        return runner([sys.executable, "tools/run_example.py", "--project", str(folder), *extra],
                      cwd=root, env=sdk_env(toolchain), check=False).returncode
    if not example:
        raise CliError(say(lang, "cmd.run_needs_example"))
    check_examples(root, [example], lang)
    return runner([sys.executable, "tools/run_example.py", example, *extra],
                  cwd=root, env=sdk_env(toolchain), check=False).returncode


# --------------------------------------------------------- new / config

YES = {"es": {"s", "si", "sí", "y", "yes"}, "en": {"y", "yes", "s"}}


def ask_until_valid(args, lang: str, key: str, default: str, convert):
    """Ask one question until `convert` accepts the answer; EOF aborts."""
    for _ in range(5):
        try:
            answer = args.ask(say(lang, key, default=default)).strip() or default
        except EOFError as error:
            raise CliError(say(lang, "new.aborted")) from error
        try:
            return convert(answer)
        except gp.ProjectError as error:
            print(say(lang, "new.invalid", reason=error), file=sys.stderr)
    raise CliError(say(lang, "new.aborted"))


def interactive_spec(args, lang: str) -> gp.Spec:
    def as_name(value):
        return gp.validate(gp.Spec(value, "X")).name

    def as_profile(value):
        choice = {"1": "standard", "2": "experimental"}.get(value, value.lower())
        return gp.validate(gp.Spec("x", "X", choice)).profile

    def as_yes(value):
        return value.strip().lower() in YES[lang]

    name = ask_until_valid(args, lang, "new.ask_name", "", as_name)
    title = ask_until_valid(args, lang, "new.ask_title", name.upper(), gp.normalize_title)
    profile = "standard"
    if len(gp.PROFILES) > 1:
        profile = ask_until_valid(args, lang, "new.ask_video", "1", as_profile)
    extended = ask_until_valid(args, lang, "new.ask_extended", "n", as_yes)
    git = ask_until_valid(args, lang, "new.ask_git", "s" if lang == "es" else "y", as_yes)
    return gp.Spec(name, title, profile, extended, git)


def new_spec(args, lang: str) -> gp.Spec:
    """Manifest, flags or questions; explicit flags override. One validation path."""
    if args.manifest:
        try:
            data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CliError(say(lang, "new.bad_manifest", reason=error)) from error
        if args.name and isinstance(data, dict):
            data = dict(data, name=args.name)
        spec = gp.spec_from_manifest(data)
    elif args.name:
        spec = gp.Spec(args.name, args.name)
    elif args.interactive:
        spec = interactive_spec(args, lang)
    else:
        raise CliError(say(lang, "new.needs_input"))
    changes = {}
    if args.title is not None:
        changes["title"] = args.title
    if args.profile is not None:
        changes["profile"] = args.profile
    if args.extended_memory is not None:
        changes["extended_memory"] = args.extended_memory
    if args.no_git:
        changes["git"] = False
    return gp.validate(dataclasses.replace(spec, **changes))


def write_files(folder: Path, files: dict[str, bytes]) -> None:
    for relative, content in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def git_first_commit(folder: Path, lang: str, runner: Runner) -> None:
    """Independent repository with the first commit; never fails the creation."""
    steps = (["git", "-c", "init.defaultBranch=main", "init", "-q"],
             ["git", "add", "-A"],
             ["git", "commit", "-q", "-m", "Initial project from glasnost (template ecs-welcome)"])
    for command in steps:
        try:
            result = runner(command, cwd=folder, capture_output=True, check=False)
        except OSError:
            result = None
        if result is None or result.returncode != 0:
            print(say(lang, "new.git_failed", path=folder), file=sys.stderr)
            return


def cmd_new(args, root: Path, lang: str, runner: Runner) -> int:
    spec = new_spec(args, lang)
    base = Path(args.dir).resolve() if args.dir else root / "projects"
    folder = base / spec.name
    if folder.exists() or folder.is_symlink():
        raise CliError(say(lang, "new.exists", path=folder))
    toolchain = None if args.no_build else resolve_toolchain(root, load_lock(root, lang), lang)
    files = gp.render_project(spec, sdk_version(root, runner), lang)
    new_dirs = [d for d in (base, *base.parents) if not d.exists()]  # deepest last
    base.mkdir(parents=True, exist_ok=True)
    folder.mkdir()
    try:
        write_files(folder, files)
        if toolchain is not None:
            code = build_project(folder, toolchain, root, lang, runner)
            if code != 0:
                raise CliError(say(lang, "new.build_failed", code=code))
        if spec.git:
            git_first_commit(folder, lang, runner)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)  # we created it a moment ago: it did not exist
        for directory in new_dirs:  # only the levels this command created, innermost first
            with contextlib.suppress(OSError):
                directory.rmdir()
        raise
    print(say(lang, "new.done", name=spec.name, path=folder, amsdos=spec.amsdos_name))
    return 0


def config_summary(meta: dict, example: dict) -> list[str]:
    return [f"title: {meta.get('title')}", f"profile: {gp.profile_key(example.get('profile', ''))}",
            f"extended_memory: {str(example.get('extended_memory', False)).lower()}",
            f"amsdos_name: {example.get('amsdos_name')}"]


def cmd_config(args, root: Path, lang: str, runner: Runner) -> int:
    folder = current_project(args)
    if not folder:
        raise CliError(say(lang, "proj.not_in_project"))
    just_show = args.title is None and args.profile is None and args.extended_memory is None
    try:
        meta, example = gp.load_project(folder)
        found = gp.project_format(meta)
        if found > gp.FORMAT:  # never rewrite what a newer glasnost generated
            raise gp.ProjectError(gp.newer_format_message(found))
        if just_show:
            print("\n".join(config_summary(meta, example)))
        new_files = gp.apply_config(folder, title=args.title, profile=args.profile,
                                    extended_memory=args.extended_memory)
    except gp.ProjectError as error:
        raise CliError(say(lang, "proj.config_invalid", reason=error)) from error
    if just_show:
        # No options: bring only the generated files up to date. This is what `build` asks for
        # when it says "run glasnost config" (after editing components or modules in example.json);
        # the documents the user edits (example.json, glasnost.project.json) stay byte for byte.
        new_files = {rel: content for rel, content in new_files.items() if rel.startswith("generated/")}
    changed = [rel for rel, content in sorted(new_files.items())
               if not (folder / rel).is_file() or (folder / rel).read_bytes() != content]
    if not changed:
        if not just_show:
            print(say(lang, "proj.config_nochange"))
        return 0
    for rel in changed:
        print(say(lang, "proj.config_regen" if just_show else "proj.config_file", path=rel))
    if args.dry_run:
        print(say(lang, "proj.config_dry"))
        return 0
    write_replacing(folder, {rel: new_files[rel] for rel in changed})
    print(say(lang, "proj.config_regenerated" if just_show else "proj.config_done"))
    return 0


def write_replacing(folder: Path, files: dict[str, bytes]) -> None:
    """Write every file next to its target first, then swap them in (atomic per file)."""
    staged = []
    try:
        for rel, content in files.items():
            target = folder / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".glasnost-tmp")
            temporary.write_bytes(content)
            staged.append((temporary, target))
        for temporary, target in staged:
            os.replace(temporary, target)
    finally:
        for temporary, _target in staged:
            temporary.unlink(missing_ok=True)


# ------------------------------------------------ update / rollback / projects

UPDATE_BRANCH = "glasnost-update-"


def git_run(runner: Runner, folder: Path, *args: str) -> "subprocess.CompletedProcess[str]":
    return runner(["git", "-C", str(folder), *args], capture_output=True, check=False)


def project_repo(folder: Path, lang: str, runner: Runner) -> str:
    """Name of the checked-out branch of the project's own repository, or a clear error."""
    top = git_run(runner, folder, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != folder.resolve():
        raise CliError(say(lang, "update.needs_repo", path=folder))
    branch = git_run(runner, folder, "branch", "--show-current").stdout.strip()
    if not branch:
        raise CliError(say(lang, "update.detached"))
    return branch


def require_clean(folder: Path, lang: str, runner: Runner) -> None:
    status = git_run(runner, folder, "status", "--porcelain")
    if status.returncode != 0 or status.stdout.strip():
        lines = "\n".join("  " + line for line in status.stdout.splitlines()[:10])
        raise CliError(say(lang, "update.dirty", path=folder) + ("\n" + lines if lines else ""))


def print_plan(plan: gu.Plan, lang: str) -> None:
    print(say(lang, "update.plan", name=plan.folder.name, a=plan.from_format, b=plan.to_format))
    for step in plan.steps:
        print(say(lang, "update.step", a=step.from_format, b=step.from_format + 1, summary=step.summary))
    for path in plan.changed:
        print(say(lang, "update.rewrite", path=path))
    for task in plan.tasks:
        print(say(lang, "update.task", task=task))


def restore_branch(folder: Path, base: str, branch: str, backups: dict[str, bytes | None],
                   new_dirs: list[Path], runner: Runner, lang: str) -> None:
    """Back to the starting branch exactly as it was, and drop the update branch.

    `backups` holds the bytes of every file the update was going to write (None when it did not
    exist): they are put back even when Git does not track them (a gitignored generated/).
    """
    ok = git_run(runner, folder, "switch", "-q", "-f", base).returncode == 0  # only our own changes die
    for relative, content in backups.items():
        target = folder / relative
        if content is None:
            target.unlink(missing_ok=True)
        elif not target.is_file() or target.read_bytes() != content:
            target.write_bytes(content)
    for directory in new_dirs:  # innermost first
        with contextlib.suppress(OSError):
            directory.rmdir()
    ok = git_run(runner, folder, "branch", "-q", "-D", branch).returncode == 0 and ok
    if not ok:
        print(say(lang, "update.restore_failed", base=base, branch=branch), file=sys.stderr)


def cmd_update(args, root: Path, lang: str, runner: Runner) -> int:
    folder = current_project(args, lang)
    if not folder:
        raise CliError(say(lang, "proj.not_in_project"))
    try:
        plan = gu.plan_update(folder, sdk_version(root, runner))
    except gu.UpdateError as error:
        raise CliError(say(lang, "update.cannot_plan", reason=error)) from error
    if plan.empty:
        print(say(lang, "update.up_to_date", name=folder.name, a=plan.from_format))
        return 0
    print_plan(plan, lang)
    if args.dry_run:
        print(say(lang, "update.dry_run"))
        return 0

    toolchain = resolve_toolchain(root, load_lock(root, lang), lang)  # before anything is touched
    base = project_repo(folder, lang, runner)
    require_clean(folder, lang, runner)
    branch = f"{UPDATE_BRANCH}{plan.from_format}-to-{plan.to_format}"
    if git_run(runner, folder, "rev-parse", "--verify", "-q", f"refs/heads/{branch}").returncode == 0:
        raise CliError(say(lang, "update.branch_exists", branch=branch))
    if git_run(runner, folder, "switch", "-q", "-c", branch).returncode != 0:
        raise CliError(say(lang, "update.git_failed", step="switch -c"))
    backups = {path: ((folder / path).read_bytes() if (folder / path).is_file() else None)
               for path in plan.changed}
    new_dirs = sorted({parent for path in plan.changed if backups[path] is None
                       for parent in (folder / path).parents
                       if parent != folder and folder in parent.parents and not parent.exists()},
                      key=lambda p: len(p.parts), reverse=True)

    build_code = 0
    try:
        if git_run(runner, folder, "config", f"branch.{branch}.glasnostBase", base).returncode != 0:
            raise CliError(say(lang, "update.git_failed", step="config"))
        write_replacing(folder, {path: plan.files[path] for path in plan.changed})
        problems = gp.check_project(folder)
        if problems:
            raise CliError(say(lang, "proj.check_failed", path=folder) + "\n"
                           + "\n".join(f"  - {p}" for p in problems))
        build_code = build_project(folder, toolchain, root, lang, runner)
        if build_code != 0 and not plan.tasks:
            raise CliError(say(lang, "update.build_failed", code=build_code, base=base))
        message = (f"glasnost update: project format {plan.from_format} to {plan.to_format}\n\n"
                   + "\n".join(f"- {step.summary}" for step in plan.steps)
                   + ("\n\nManual tasks:\n" + "\n".join(f"- {task}" for task in plan.tasks)
                      if plan.tasks else ""))
        if (git_run(runner, folder, "add", "-A").returncode != 0
                or git_run(runner, folder, "commit", "-q", "-m", message).returncode != 0):
            raise CliError(say(lang, "update.commit_failed", base=base))
    except BaseException:  # failure, write error, Ctrl-C: everything goes back as it was
        restore_branch(folder, base, branch, backups, new_dirs, runner, lang)
        raise
    print(say(lang, "update.done", a=plan.from_format, b=plan.to_format, branch=branch, base=base))
    if plan.tasks:
        print(say(lang, "update.tasks_pending", count=len(plan.tasks)))
        return 3 if build_code != 0 else 0
    return 0


def cmd_rollback(args, root: Path, lang: str, runner: Runner) -> int:
    """Leave an update branch and go back to the branch it started from. Loses nothing."""
    folder = current_project(args, lang)
    if not folder:
        raise CliError(say(lang, "proj.not_in_project"))
    branch = project_repo(folder, lang, runner)
    found = git_run(runner, folder, "config", "--get", f"branch.{branch}.glasnostBase")
    base = found.stdout.strip() if found.returncode == 0 else ""
    if not branch.startswith(UPDATE_BRANCH) or not base:
        raise CliError(say(lang, "rollback.not_update_branch", branch=branch))
    require_clean(folder, lang, runner)
    if git_run(runner, folder, "switch", "-q", base).returncode != 0:
        raise CliError(say(lang, "rollback.base_missing", base=base))
    if args.delete:
        counted = git_run(runner, folder, "rev-list", "--count", f"{base}..{branch}").stdout.strip()
        extra = int(counted) - 1 if counted.isdigit() else 1  # the update commit itself is not "yours"
        if extra > 0:  # never silently drop commits the user added on the update branch
            print(say(lang, "rollback.delete_refused", base=base, branch=branch, count=extra), file=sys.stderr)
            return 1
        git_run(runner, folder, "branch", "-q", "-D", branch)
        print(say(lang, "rollback.deleted", base=base, branch=branch))
    else:
        print(say(lang, "rollback.kept", base=base, branch=branch))
    return 0


def cmd_projects(args, root: Path, lang: str, runner: Runner) -> int:
    base = Path(args.dir).resolve() if args.dir else root / "projects"
    rows = []
    if base.is_dir():
        for folder in sorted(base.iterdir()):
            if folder.is_symlink() or not (folder / gp.PROJECT_FILE).is_file():
                continue
            try:
                meta, _example = gp.load_project(folder)
                found = gp.project_format(meta)
                status = ("current" if found == gp.FORMAT else
                          "outdated" if found < gp.FORMAT else "newer")
                status = say(lang, f"projects.{status}", a=found, b=gp.FORMAT)
            except gp.ProjectError as error:
                status = say(lang, "projects.invalid", reason=error)
            branch = git_run(runner, folder, "branch", "--show-current").stdout.strip() or "-"
            dirty = git_run(runner, folder, "status", "--porcelain").stdout.strip()
            rows.append((folder.name, status, branch + (" *" if dirty else "")))
    if not rows:
        print(say(lang, "projects.none", path=base))
        return 0
    width = max(len(name) for name, _s, _b in rows)
    for name, status, branch in rows:
        print(f"  {name:<{width}}  {branch:<28}  {status}")
    return 0


def cmd_path(args, root: Path, lang: str, runner: Runner) -> int:
    print(say(lang, "cmd.path", path=resolve_toolchain(root, load_lock(root, lang), lang).path))
    return 0


def cmd_version(args, root: Path, lang: str, runner: Runner) -> int:
    print(sdk_version(root, runner))
    return 0


# ------------------------------------------------------------------- main

def build_parser(lang: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="glasnost", description=say(lang, "help.description"))
    parser.add_argument("--lang", choices=LANGS, help=say(lang, "help.lang"))
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help=say(lang, "help.doctor"))
    doctor.add_argument("--network", action="store_true", help=say(lang, "help.network"))
    doctor.set_defaults(func=cmd_doctor)

    install_deps = sub.add_parser("install-deps", help=say(lang, "help.install_deps"))
    install_deps.add_argument("--yes", action="store_true", help=say(lang, "help.install_deps_yes"))
    install_deps.set_defaults(func=cmd_install_deps)

    install = sub.add_parser("install-toolchain", help=say(lang, "help.install"))
    install.add_argument("--dry-run", action="store_true", help=say(lang, "help.install_dry"))
    install.add_argument("--force", action="store_true", help=say(lang, "help.install_force"))
    install.set_defaults(func=cmd_install)

    sub.add_parser("toolchains", help=say(lang, "help.toolchains")).set_defaults(func=cmd_toolchains)

    clean = sub.add_parser("clean-toolchains", help=say(lang, "help.clean"))
    clean.add_argument("--yes", action="store_true", help=say(lang, "help.clean_yes"))
    clean.add_argument("--keep", action="append", default=[], metavar="REV", help=say(lang, "help.clean_keep"))
    clean.set_defaults(func=cmd_clean)

    for name, func, key in (("install-cli", cmd_install_cli, "help.install_cli"),
                            ("uninstall-cli", cmd_uninstall_cli, "help.uninstall_cli")):
        cli = sub.add_parser(name, help=say(lang, key))
        cli.add_argument("--prefix", help=say(lang, "help.prefix"))
        if name == "install-cli":
            cli.add_argument("--dry-run", action="store_true", help=say(lang, "help.install_dry"))
            cli.add_argument("--force", action="store_true", help=say(lang, "help.cli_force"))
        cli.set_defaults(func=func)

    new = sub.add_parser("new", help=say(lang, "help.new"))
    new.add_argument("name", nargs="?", help=say(lang, "help.new_name"))
    new.add_argument("--manifest", metavar="FILE", help=say(lang, "help.new_manifest"))
    new.add_argument("--title", help=say(lang, "help.title"))
    new.add_argument("--profile", choices=sorted(gp.PROFILES), help=say(lang, "help.profile"))
    memory = new.add_mutually_exclusive_group()
    memory.add_argument("--extended-memory", dest="extended_memory", action="store_true", default=None,
                        help=say(lang, "help.extended"))
    memory.add_argument("--no-extended-memory", dest="extended_memory", action="store_false",
                        help=say(lang, "help.no_extended"))
    new.add_argument("--dir", metavar="DIR", help=say(lang, "help.new_dir"))
    new.add_argument("--no-git", action="store_true", help=say(lang, "help.no_git"))
    new.add_argument("--no-build", action="store_true", help=say(lang, "help.no_build"))
    new.set_defaults(func=cmd_new)

    config = sub.add_parser("config", help=say(lang, "help.config"))
    config.add_argument("--project", metavar="DIR", help=say(lang, "help.project"))
    config.add_argument("--title", help=say(lang, "help.title"))
    config.add_argument("--profile", choices=sorted(gp.PROFILES), help=say(lang, "help.profile"))
    cmemory = config.add_mutually_exclusive_group()
    cmemory.add_argument("--extended-memory", dest="extended_memory", action="store_true", default=None,
                         help=say(lang, "help.extended"))
    cmemory.add_argument("--no-extended-memory", dest="extended_memory", action="store_false",
                         help=say(lang, "help.no_extended"))
    config.add_argument("--dry-run", action="store_true", help=say(lang, "help.config_dry"))
    config.set_defaults(func=cmd_config)

    update = sub.add_parser("update", help=say(lang, "help.update"))
    update.add_argument("--project", metavar="DIR", help=say(lang, "help.project"))
    update.add_argument("--dry-run", action="store_true", help=say(lang, "help.update_dry"))
    update.set_defaults(func=cmd_update)

    rollback = sub.add_parser("rollback", help=say(lang, "help.rollback"))
    rollback.add_argument("--project", metavar="DIR", help=say(lang, "help.project"))
    rollback.add_argument("--delete", action="store_true", help=say(lang, "help.rollback_delete"))
    rollback.set_defaults(func=cmd_rollback)

    projects = sub.add_parser("projects", help=say(lang, "help.projects"))
    projects.add_argument("--dir", metavar="DIR", help=say(lang, "help.new_dir"))
    projects.set_defaults(func=cmd_projects)

    build = sub.add_parser("build", help=say(lang, "help.build"))
    build.add_argument("examples", nargs="*", help=say(lang, "help.examples"))
    build.add_argument("--project", metavar="DIR", help=say(lang, "help.project"))
    build.set_defaults(func=cmd_build)

    test = sub.add_parser("test", help=say(lang, "help.test"))
    test.add_argument("--project", metavar="DIR", help=say(lang, "help.project"))
    test.set_defaults(func=cmd_test)

    run = sub.add_parser("run", help=say(lang, "help.run"))
    run.add_argument("--project", metavar="DIR", help=say(lang, "help.project"))
    run.add_argument("rest", nargs=argparse.REMAINDER, metavar="[example] [-- options]",
                     help=say(lang, "help.rest"))
    run.set_defaults(func=cmd_run)

    sub.add_parser("path", help=say(lang, "help.path")).set_defaults(func=cmd_path)
    sub.add_parser("version", help=say(lang, "help.version")).set_defaults(func=cmd_version)
    return parser


def main(argv: Sequence[str] | None = None, root: Path = ROOT, runner: Runner = default_runner,
         ask: Callable[[str], str] = input, interactive: bool | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    flag = None
    for index, token in enumerate(argv):
        if token == "--lang" and index + 1 < len(argv):
            flag = argv[index + 1]
        elif token.startswith("--lang="):
            flag = token.split("=", 1)[1]
    args = build_parser(pick_language(flag)).parse_args(argv)
    lang = pick_language(args.lang)
    args.lang_resolved = lang
    args.ask = ask
    args.interactive = sys.stdin.isatty() if interactive is None else interactive
    try:
        return args.func(args, root, lang, runner)
    except CliError as error:
        print(str(error), file=sys.stderr)
        return 1
    except gp.ProjectError as error:
        print(say(lang, "cmd.project_error", reason=error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(say(lang, "cmd.interrupted"), file=sys.stderr)
        return 130
    except OSError as error:
        print(say(lang, "cmd.os_error", detail=f"{error.filename or ''} {error.strerror or error}".strip()),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
