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
from glasnost_i18n import LANGS, pick_language, say  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LOCKFILE = "toolchain.lock.json"
COMPLETE_MARKER = ".glasnost-complete"
MIN_PYTHON = (3, 10)
BOOST_HEADER = Path("/usr/include/boost/version.hpp")
BUILD_TOOLS = ("git", "make", "gcc", "g++", "bison", "flex")

# Built by install-toolchain, in this order (same list as the release workflow).
# Paths are relative to the `cpctelera/` directory of the checkout; "." is the library.
MAKE_STEPS = (
    "tools/sdcc-4.5.0",
    "tools/hex2bin-2.0",
    "tools/iDSK-0.13",
    "tools/2cdt",
    "tools/cpc2cdt",
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


def cmd_build(args, root: Path, lang: str, runner: Runner) -> int:
    toolchain = resolve_toolchain(root, load_lock(root, lang), lang)
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
    return runner(["make", "test", f"PYTHON={sys.executable}"],
                  cwd=root, env=sdk_env(toolchain), check=False).returncode


def cmd_run(args, root: Path, lang: str, runner: Runner) -> int:
    toolchain = resolve_toolchain(root, load_lock(root, lang), lang)
    check_examples(root, [args.example], lang)
    extra = args.rest  # argparse already consumed the separating "--"
    return runner([sys.executable, "tools/run_example.py", args.example, *extra],
                  cwd=root, env=sdk_env(toolchain), check=False).returncode


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

    install = sub.add_parser("install-toolchain", help=say(lang, "help.install"))
    install.add_argument("--dry-run", action="store_true", help=say(lang, "help.install_dry"))
    install.add_argument("--force", action="store_true", help=say(lang, "help.install_force"))
    install.set_defaults(func=cmd_install)

    build = sub.add_parser("build", help=say(lang, "help.build"))
    build.add_argument("examples", nargs="*", help=say(lang, "help.examples"))
    build.set_defaults(func=cmd_build)

    test = sub.add_parser("test", help=say(lang, "help.test"))
    test.set_defaults(func=cmd_test)

    run = sub.add_parser("run", help=say(lang, "help.run"))
    run.add_argument("example", help=say(lang, "help.example"))
    run.add_argument("rest", nargs=argparse.REMAINDER, help=say(lang, "help.rest"))
    run.set_defaults(func=cmd_run)

    sub.add_parser("path", help=say(lang, "help.path")).set_defaults(func=cmd_path)
    sub.add_parser("version", help=say(lang, "help.version")).set_defaults(func=cmd_version)
    return parser


def main(argv: Sequence[str] | None = None, root: Path = ROOT, runner: Runner = default_runner) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    flag = None
    for index, token in enumerate(argv):
        if token == "--lang" and index + 1 < len(argv):
            flag = argv[index + 1]
        elif token.startswith("--lang="):
            flag = token.split("=", 1)[1]
    args = build_parser(pick_language(flag)).parse_args(argv)
    lang = pick_language(args.lang)
    try:
        return args.func(args, root, lang, runner)
    except CliError as error:
        print(str(error), file=sys.stderr)
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
