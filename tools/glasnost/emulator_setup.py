"""Find, download and remember the CPC emulator that `glasnost run` opens.

Pure logic, no printing and no prompts (those live in tools/glasnost/glasnost.py), so it is easy to test.

The choice is kept in `tools/emulators/emulator.json` inside the SDK (gitignored, like
`.toolchain/`): nothing outside the checkout is touched, and the next `glasnost run` (or
`make run`) reads it without asking anything. Downloaded emulators live next to it.

Retro Virtual Machine is fetched from its official host. The release assets are pinned by
size and SHA-256 below, so a changed or corrupted download is rejected instead of installed.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
CONFIG_NAME = "emulator.json"
CONFIG_VERSION = 1

RVM_VERSION = "2.1.20"
RVM_BASE = f"https://static.retrovm.org/release/{RVM_VERSION}/"
RVM_ASSETS = {
    "linux-x86_64": {
        "file": f"RetroVirtualMachine.{RVM_VERSION}.Linux.x64.zip",
        "size": 93136928,
        "sha256": "fd00b31cdd194fdbe2f80006b5042c5825c29afa55ae751f6f8e015a1ca5050b",
    },
    "linux-aarch64": {
        "file": f"RetroVirtualMachine.{RVM_VERSION}.Linux.arm64.zip",
        "size": 93113212,
        "sha256": "6c0a68e28036f905f058fc0cb182bf2deb0af06b8120262dbe672e6e671db574",
    },
    "windows-x86_64": {
        "file": f"RetroVirtualMachine.{RVM_VERSION}.Windows.x64.zip",
        "size": 92549080,
        "sha256": "3766694cf5f292953bf5c3f36efb7a896125890c9bfa5179e5f46625b69aa3c9",
    },
    "macos": {
        "file": f"RetroVirtualMachine.{RVM_VERSION}.dmg",
        "size": 190743240,
        "sha256": "01d3d60e419c1dcbaf7185aa465ea60dd072c0d3205792f0ea6adb97d4d78301",
    },
}

BLUEPIXEL_REPO = "johnlobo/BluePixel"
BLUEPIXEL_API = f"https://api.github.com/repos/{BLUEPIXEL_REPO}/releases/latest"

# Command names looked up in the PATH, in the order they are offered.
EMULATOR_COMMANDS = ("amspirit-lite", "amspirit", "RetroVirtualMachine", "retrovirtualmachine",
                     "bluepixel")
MAC_APPS = ("Retro Virtual Machine 2.app", "RetroVirtualMachine.app", "BluePixel.app")

# Retro Virtual Machine is launched the way CPCtelera's tools/scripts/cpct_rvm does it:
#   RVM -ns -b=<machine> (-i= FILE | -s FILE) [-p -w] [-c=<command>\n]
# That script targeted RVM 2.0 beta r7; it was not run against 2.1.20 here. RVM has no known
# option for a symbols file, so none is passed. `"args"` in emulator.json overrides the whole
# command line ({image} = the CDT/DSK/SNA, {name} = the 8-character program name).
RVM_MACHINES = {".cdt": "cpc464", ".sna": "cpc464", ".dsk": "cpc6128"}   # 6128: the extended-memory examples

Opener = Callable[..., object]
Progress = Callable[[int, int], None]


class SetupError(Exception):
    """An error with a message key and values; tools/glasnost/glasnost.py translates it."""

    def __init__(self, key: str, **values: object) -> None:
        super().__init__(key)
        self.key = key
        self.values = values


# ------------------------------------------------------------------ config

def emulators_dir(root: Path = ROOT) -> Path:
    return root / "tools" / "emulators"


def config_path(root: Path = ROOT) -> Path:
    return emulators_dir(root) / CONFIG_NAME


def read_config(root: Path = ROOT) -> dict | None:
    """The saved config with every field of a wrong type dropped (a hand-edited file must not crash)."""
    try:
        data = json.loads(config_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    for key in ("path", "kind", "version", "source", "sha256"):
        if key in data and not isinstance(data[key], str):
            del data[key]
    if "args" in data and not (isinstance(data["args"], list) and all(isinstance(a, str) for a in data["args"])):
        del data["args"]
    return data


def saved_path(root: Path, data: dict) -> Path | None:
    """The saved executable as an absolute path (paths inside the SDK are stored relative to it)."""
    path = data.get("path")
    if not path:
        return None
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def _storable(root: Path, path: Path) -> str:
    """Paths inside the SDK are kept relative, so moving or copying the SDK keeps them valid."""
    path = path.absolute()
    try:
        return path.relative_to(root.absolute()).as_posix()
    except ValueError:
        return str(path)


def write_config(root: Path, data: dict) -> None:
    folder = emulators_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    temp = config_path(root).with_suffix(".tmp")
    temp.write_text(json.dumps({"version": CONFIG_VERSION, **data}, indent=2) + "\n", encoding="utf-8")
    temp.replace(config_path(root))


def configured(root: Path = ROOT) -> Path | None:
    """The saved emulator, if it is still there."""
    data = read_config(root) or {}
    candidate = saved_path(root, data)
    if data.get("declined") or candidate is None:
        return None
    return candidate if candidate.is_file() else None


def stale_path(root: Path = ROOT) -> str | None:
    """A saved emulator path that no longer exists (to tell the user why we ask again)."""
    data = read_config(root) or {}
    candidate = saved_path(root, data)
    if candidate is not None and not data.get("declined") and not candidate.is_file():
        return str(candidate)
    return None


def declined(root: Path = ROOT) -> bool:
    return bool((read_config(root) or {}).get("declined"))


def save_emulator(root: Path, path: Path, kind: str | None = None, **extra: object) -> None:
    write_config(root, {"kind": kind or kind_of(path), "path": _storable(root, Path(path)), **extra})


def save_declined(root: Path) -> None:
    write_config(root, {"declined": True})


def reset(root: Path = ROOT) -> bool:
    try:
        config_path(root).unlink()
    except FileNotFoundError:
        return False
    return True


# --------------------------------------------------------------- discovery

def kind_of(path: Path | str) -> str:
    name = Path(path).name.lower()
    if "retrovirtualmachine" in name or name == "rvm":
        return "rvm"
    if "bluepixel" in name:
        return "bluepixel"
    return "generic"


def app_binary(path: Path) -> Path | None:
    """The executable inside a macOS .app bundle."""
    macos = path / "Contents" / "MacOS"
    if not macos.is_dir():
        return None
    files = sorted(p for p in macos.iterdir() if p.is_file())
    preferred = [p for p in files if p.stem.lower() == path.stem.lower().replace(" ", "")]
    return (preferred or files or [None])[0]


def is_runnable(path: Path) -> bool:
    return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))


def normalize(text: str) -> Path:
    """A path typed by the user -> the executable (resolving a macOS .app)."""
    path = Path(text.strip().strip('"').strip("'")).expanduser().absolute()
    if path.is_dir() and path.suffix == ".app":
        inner = app_binary(path)
        if inner is None:
            raise SetupError("emu.bad_path", path=path)
        path = inner
    if not is_runnable(path):
        raise SetupError("emu.bad_path", path=path)
    return path


def candidates(root: Path = ROOT, home: Path | None = None, path_env: str | None = None) -> list[Path]:
    """Emulators that look usable on this machine, best guess first, without duplicates."""
    home = home or Path.home()
    found: list[Path] = []

    def add(path: Path | None) -> None:
        if path is not None and is_runnable(path) and path not in found:
            found.append(path)

    add(root.parent / "tools" / "amspirit-lite" / "run.sh")
    for command in EMULATOR_COMMANDS:
        located = shutil.which(command, path=path_env)
        add(Path(located) if located else None)
    for base in (Path("/Applications"), home / "Applications"):
        for app in MAC_APPS:
            if (base / app).is_dir():
                add(app_binary(base / app))
    downloaded = emulators_dir(root)
    if downloaded.is_dir():
        for pattern in ("*/RetroVirtualMachine", "*/RetroVirtualMachine.exe"):
            for exe in sorted(downloaded.glob(pattern)):
                add(exe)
        for app in sorted(downloaded.glob("*/*.app")) + sorted(downloaded.glob("*/*/BluePixel.app")):
            add(app_binary(app))
    return found


# ---------------------------------------------------------------- download

def platform_key(system: str | None = None, machine: str | None = None) -> str | None:
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        return {"x86_64": "linux-x86_64", "amd64": "linux-x86_64",
                "aarch64": "linux-aarch64", "arm64": "linux-aarch64"}.get(machine)
    if system == "windows":
        return "windows-x86_64" if machine in ("amd64", "x86_64") else None
    return None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def default_opener(url: str):
    headers = {"User-Agent": "glasnost-sdk"}   # GitHub's API refuses requests without one
    if url.startswith("https://api.github.com/"):
        headers["Accept"] = "application/vnd.github+json"   # any other Accept gets a 415
    request = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(request, timeout=60)


def download(url: str, destination: Path, size: int, sha256: str, opener: Opener | None = None,
             progress: Progress | None = None) -> None:
    """Fetch `url` to `destination`, verifying its SHA-256. A bad file is never left in place."""
    opener = opener or default_opener
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    digest, done = hashlib.sha256(), 0
    try:
        with opener(url) as response, part.open("wb") as out:
            total = int(getattr(response, "length", None) or size)
            for block in iter(lambda: response.read(1 << 20), b""):
                out.write(block)
                digest.update(block)
                done += len(block)
                if progress:
                    progress(done, total)
        if digest.hexdigest() != sha256:
            raise SetupError("emu.sha_mismatch", expected=sha256, actual=digest.hexdigest())
    except (OSError, http.client.HTTPException) as error:   # URLError, timeouts, IncompleteRead
        part.unlink(missing_ok=True)
        raise SetupError("emu.download_failed", url=url, reason=error) from error
    except BaseException:                                    # SetupError, Ctrl-C: never leave a partial file
        part.unlink(missing_ok=True)
        raise
    part.replace(destination)


def _safe_extract(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    base = target.resolve()
    with zipfile.ZipFile(archive) as bundle:
        members = [name for name in bundle.namelist() if not name.startswith("__MACOSX/")]   # Finder junk
        for member in members:
            if not (base / member).resolve().is_relative_to(base):
                raise SetupError("emu.unsafe_archive", name=member)
        bundle.extractall(target, members)


def _extract_dmg(archive: Path, target: Path, run: Callable = subprocess.run) -> None:
    """macOS only: mount the image, copy the .app out, unmount."""
    mount = Path(tempfile.mkdtemp(prefix="glasnost-dmg-"))
    attached = False
    try:
        result = run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mount), str(archive)],
                     capture_output=True, text=True)
        if result.returncode:
            raise SetupError("emu.dmg_failed", reason=(result.stderr or "").strip())
        attached = True
        apps = sorted(mount.glob("*.app"))
        if not apps:
            raise SetupError("emu.no_exe", path=mount)
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(apps[0], target / apps[0].name, symlinks=True, dirs_exist_ok=True)
    finally:
        still_mounted = False
        if attached:
            detach = run(["hdiutil", "detach", "-quiet", str(mount)], capture_output=True)
            if detach.returncode:
                forced = run(["hdiutil", "detach", "-force", str(mount)], capture_output=True)
                still_mounted = bool(forced.returncode)
        if not still_mounted:   # removing a mounted volume's directory would fail or be wrong
            shutil.rmtree(mount, ignore_errors=True)


def _find_executable(folder: Path, key: str) -> Path | None:
    if key == "macos":
        apps = sorted(folder.glob("*.app"))
        return app_binary(apps[0]) if apps else None
    name = "RetroVirtualMachine.exe" if key.startswith("windows") else "RetroVirtualMachine"
    return next((p for p in sorted(folder.rglob(name)) if p.is_file()), None)


def _install_archive(root: Path, folder: Path, archive_name: str, url: str, size: int, sha256: str,
                     extract: Callable[[Path, Path], None], find: Callable[[Path], Path | None],
                     opener: Opener | None, progress: Progress | None,
                     log: Callable[[str, dict], None] | None) -> Path:
    """Download, verify, extract (staged, then renamed) and return the emulator executable."""
    executable = find(folder) if folder.is_dir() else None
    if executable is not None:
        return executable
    archive = emulators_dir(root) / "downloads" / archive_name
    if not (archive.is_file() and sha256_of(archive) == sha256):
        if log:
            log("emu.downloading", {"url": url})
        download(url, archive, size, sha256, opener, progress)
    if log:
        log("emu.verified", {})
        log("emu.extracting", {"path": folder})
    # Extract beside the final folder and rename on success: an interrupted extraction must
    # never look like an installed emulator.
    staging = folder.with_name(folder.name + ".part")
    shutil.rmtree(staging, ignore_errors=True)
    try:
        extract(archive, staging)
        if find(staging) is None:
            raise SetupError("emu.no_exe", path=staging)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(folder, ignore_errors=True)
    staging.rename(folder)
    executable = find(folder)
    if os.name != "nt":
        executable.chmod(executable.stat().st_mode | 0o111)   # zip extraction does not keep the mode
    archive.unlink(missing_ok=True)   # the extracted copy is what is used; do not keep it twice
    return executable


def install_rvm(root: Path = ROOT, system: str | None = None, machine: str | None = None,
                opener: Opener | None = None, progress: Progress | None = None,
                run: Callable = subprocess.run, log: Callable[[str, dict], None] | None = None) -> Path:
    """Download Retro Virtual Machine for this platform into tools/emulators/ and save it."""
    key = platform_key(system, machine)
    if key is None:
        raise SetupError("emu.no_rvm_platform", platform=f"{system or platform.system()} {machine or platform.machine()}")
    asset = RVM_ASSETS[key]
    url = RVM_BASE + asset["file"]
    folder = emulators_dir(root) / f"retro-virtual-machine-{RVM_VERSION}-{key}"
    extract = (lambda archive, target: _extract_dmg(archive, target, run)) if key == "macos" else _safe_extract
    executable = _install_archive(root, folder, asset["file"], url, asset["size"], asset["sha256"], extract,
                                  lambda where: _find_executable(where, key), opener, progress, log)
    save_emulator(root, executable, "rvm", version=RVM_VERSION, source=url, sha256=asset["sha256"])
    return executable


# --------------------------------------------------------------- BluePixel

def bluepixel_supported(system: str | None = None, machine: str | None = None) -> bool:
    """BluePixel is a macOS app; its releases are built for Apple Silicon."""
    return ((system or platform.system()).lower() == "darwin"
            and (machine or platform.machine()).lower() in ("arm64", "aarch64"))


def _find_bluepixel(folder: Path) -> Path | None:
    for app in sorted(folder.glob("BluePixel.app")) + sorted(folder.glob("*/BluePixel.app")):
        binary = app_binary(app)
        if binary is not None:
            return binary
    return None


def latest_bluepixel(opener: Opener | None = None) -> dict:
    """The newest GitHub release's macOS arm64 zip: {tag, url, name, size, sha256}.

    The SHA-256 is the digest GitHub publishes for the asset; a release without one is refused,
    because there would be nothing to verify the download against.
    """
    opener = opener or default_opener
    try:
        with opener(BLUEPIXEL_API) as response:
            release = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, http.client.HTTPException) as error:
        raise SetupError("emu.download_failed", url=BLUEPIXEL_API, reason=error) from error
    for asset in release.get("assets", []) if isinstance(release, dict) else []:
        name = str(asset.get("name", ""))
        if name.endswith(".zip") and "macos" in name.lower() and ("arm64" in name.lower() or "universal" in name.lower()):
            digest = str(asset.get("digest") or "")
            if not digest.startswith("sha256:") or len(digest) != 71:
                raise SetupError("emu.no_digest", name=name)
            return {"tag": str(release.get("tag_name", "")), "name": name, "size": int(asset.get("size") or 0),
                    "url": str(asset.get("browser_download_url", "")), "sha256": digest[7:]}
    raise SetupError("emu.no_bluepixel_asset")


def install_bluepixel(root: Path = ROOT, system: str | None = None, machine: str | None = None,
                      opener: Opener | None = None, progress: Progress | None = None,
                      log: Callable[[str, dict], None] | None = None) -> Path:
    """Download the latest BluePixel release into tools/emulators/ and save it."""
    if not bluepixel_supported(system, machine):
        raise SetupError("emu.no_bluepixel_platform", platform=f"{system or platform.system()} {machine or platform.machine()}")
    release = latest_bluepixel(opener)
    folder = emulators_dir(root) / f"bluepixel-{release['tag']}-macos-arm64"
    executable = _install_archive(root, folder, release["name"], release["url"], release["size"], release["sha256"],
                                  _safe_extract, _find_bluepixel, opener, progress, log)
    save_emulator(root, executable, "bluepixel", version=release["tag"], source=release["url"], sha256=release["sha256"])
    return executable


# ------------------------------------------------------------------ launch

# Emulators that start a disc by themselves (/A or RUN"name typed for you): the DSK is the better image.
DISC_AUTORUN_KINDS = ("bluepixel", "rvm")


def kind_for(emulator: str, root: Path = ROOT) -> str:
    """The saved kind when `emulator` is the saved one, otherwise guessed from its name."""
    data = read_config(root) or {}
    if saved_path(root, data) == Path(emulator) and data.get("kind"):
        return data["kind"]
    return kind_of(emulator)


def preferred_image(emulator: str | None, root: Path = ROOT) -> str | None:
    return "dsk" if emulator and kind_for(emulator, root) in DISC_AUTORUN_KINDS else None


def build_command(emulator: str, image: Path, build_dir: Path, name: str, root: Path = ROOT) -> list[str]:
    """The command line that opens `image` in `emulator`. `build_dir` holds the build's obj/ folder."""
    kind = kind_for(emulator, root)
    data = read_config(root) or {}
    args = data.get("args") if saved_path(root, data) == Path(emulator) else None
    if kind == "bluepixel":   # `image [/A] [/SYM:file]`
        command = [emulator, str(image)]
        if image.suffix.lower() == ".dsk":
            command.append("/A")
        noi = build_dir / "obj" / f"{name}.noi"
        if noi.is_file():
            command.append(f"/SYM:{noi}")
        return command
    if args:
        return [emulator, *(token.replace("{image}", str(image)).replace("{name}", name[:8]) for token in args)]
    if kind == "rvm":
        return _rvm_command(emulator, image, name[:8])
    return [emulator, str(image)]


def _rvm_command(emulator: str, image: Path, program: str) -> list[str]:
    """RVM command line, copied from CPCtelera's cpct_rvm (note `-i=` and its value are two arguments)."""
    suffix = image.suffix.lower()
    command = [emulator, "-ns", f"-b={RVM_MACHINES.get(suffix, 'cpc6128')}"]
    if suffix == ".sna":
        return command + ["-s", str(image)]
    command += ["-i=", str(image)]
    if suffix == ".cdt":
        return command + ["-p", "-w", '-c=RUN"\\n \\n']
    return command + [f'-c=RUN"{program}"\\n']
