"""Offline bundle of the pinned CPCTelera Next commit (export and import).

A bundle is one `.tar` with two members, written byte-for-byte reproducibly for the
same inputs (sorted members, zero timestamps and owners):

    manifest.json           schema, source URL, commit, pack name/size/SHA-256
    cpctelera-next.pack     git pack of that one commit with its whole tree, no history

Why a pack and not `git bundle`: `install-toolchain` fetches with `--depth=1`, and git
creates a bundle from a shallow clone without any error that then fails on import with
"did not send all necessary objects". `rev-list --objects --no-walk | pack-objects` works
from a shallow clone and from a full one alike.

Trust: the only trust anchor is the commit in toolchain.lock.json. A commit hash covers its
tree, so after `index-pack --fsck-objects` (every object re-hashed) the lockfile commit
being present in the pack proves the files are the pinned ones. The SHA-256 in the manifest
only detects a damaged or truncated file; it is no signature, because it travels inside the
same file. Importing never extracts the archive: the two members are read by name.

Nothing here touches the network.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

SCHEMA = 1
KIND = "glasnost-offline-bundle"
MANIFEST_NAME = "manifest.json"
PACK_NAME = "cpctelera-next.pack"
MAX_MANIFEST = 64 * 1024
CHUNK = 1024 * 1024
REV = re.compile(r"[0-9a-f]{40}")


class BundleError(Exception):
    """A failure with a message key (see glasnost_i18n) and its values; the CLI translates it."""

    def __init__(self, key: str, **values: object):
        super().__init__(key)
        self.key = key
        self.values = values


@dataclass(frozen=True)
class Manifest:
    url: str
    rev: str
    pack_size: int
    pack_sha256: str
    glasnost: str


def bundle_name(rev: str) -> str:
    return f"glasnost-offline-{rev[:12]}.tar"


def _git(checkout: Path, *args: str, stdin=None, stdout=None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", "-C", str(checkout), *args], stdin=stdin, stdout=stdout or subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if check and result.returncode != 0:
        raise BundleError("bundle.git_failed", command=" ".join(("git", *args[:2])),
                          detail=result.stderr.decode("utf-8", "replace").strip()[-300:])
    return result


def has_commit(checkout: Path, rev: str) -> bool:
    if not (checkout / ".git").exists():
        return False
    return _git(checkout, "cat-file", "-t", rev, check=False).stdout.decode().strip() == "commit"


def build_pack(checkout: Path, rev: str, pack: Path) -> None:
    """Write the pack of `rev` and its tree, parents left out, to `pack`."""
    if not has_commit(checkout, rev):
        raise BundleError("bundle.no_commit", rev=rev, path=checkout)
    listing = _git(checkout, "rev-list", "--objects", "--no-walk", rev).stdout
    with pack.open("wb") as handle:
        result = subprocess.run(["git", "-C", str(checkout), "pack-objects", "--stdout", "--threads=1", "-q"],
                                input=listing, stdout=handle, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise BundleError("bundle.git_failed", command="git pack-objects",
                          detail=result.stderr.decode("utf-8", "replace").strip()[-300:])


def _member(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size, info.mtime, info.mode = size, 0, 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_bundle(destination: Path, url: str, rev: str, pack: Path, glasnost_version: str) -> tuple[Path, str]:
    """Write the tar to an exclusive random temp file next to `destination`; return (temp path, SHA-256).

    The caller renames it into place. Nothing exists at `destination` yet, so a failure later in the caller's
    sequence can never cost the user a bundle that was already there.
    """
    manifest = {
        "schema": SCHEMA, "kind": KIND,
        "cpctelera_next": {"url": url, "rev": rev},
        "pack": {"name": PACK_NAME, "size": pack.stat().st_size, "sha256": sha256_file(pack)},
        "glasnost": glasnost_version,
    }
    body = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    # exclusive creation with a random name, then a rename: a link planted at a guessable ".part" name
    # (the output folder defaults to the current one) is neither written through nor renamed into place
    descriptor, name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".part", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as raw, tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            archive.addfile(_member(MANIFEST_NAME, len(body)), fileobj=_BytesReader(body))
            with pack.open("rb") as handle:
                archive.addfile(_member(PACK_NAME, pack.stat().st_size), fileobj=handle)
        os.chmod(temporary, public_mode())
        return temporary, sha256_file(temporary)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_bundle(destination: Path, url: str, rev: str, pack: Path, glasnost_version: str) -> str:
    """Write the tar at `destination` and return its SHA-256."""
    temporary, digest = stage_bundle(destination, url, rev, pack, glasnost_version)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return digest


def public_mode(directory: bool = False) -> int:
    """The mode a plain `open(..., "w")` (or `mkdir`) would give; mkstemp makes files 0600 and mkdtemp 0700."""
    umask = os.umask(0)
    os.umask(umask)
    return (0o777 if directory else 0o666) & ~umask


def stage_text(destination: Path, text: str) -> Path:
    """Write `text` to an exclusive random temp file next to `destination`; the caller renames it into place."""
    descriptor, name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".part", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(text)
        os.chmod(temporary, public_mode())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def write_text_atomically(destination: Path, text: str) -> None:
    """Exclusive random temp file in the same folder, then a rename; never writes through a planted link."""
    temporary = stage_text(destination, text)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


class _BytesReader:
    def __init__(self, data: bytes):
        self._data, self._at = data, 0

    def read(self, size: int = -1) -> bytes:
        end = len(self._data) if size < 0 else self._at + size
        chunk, self._at = self._data[self._at:end], min(end, len(self._data))
        return chunk


def _parse_manifest(raw: bytes) -> Manifest:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise BundleError("bundle.manifest_utf8") from error
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as error:    # RecursionError: absurdly nested input under the size cap
        raise BundleError("bundle.manifest_json") from error
    try:
        if type(data.get("schema")) is not int or data.get("schema") != SCHEMA or data.get("kind") != KIND:
            raise ValueError("schema or kind")
        entry, pack = data["cpctelera_next"], data["pack"]
        manifest = Manifest(url=entry["url"], rev=entry["rev"], pack_size=pack["size"],
                            pack_sha256=pack["sha256"], glasnost=str(data.get("glasnost", "")))
        if pack["name"] != PACK_NAME:
            raise ValueError("pack name")
        if not (isinstance(manifest.url, str) and REV.fullmatch(manifest.rev or "")
                and type(manifest.pack_size) is int and manifest.pack_size > 0
                and re.fullmatch(r"[0-9a-f]{64}", manifest.pack_sha256 or "")):
            raise ValueError("field types")
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise BundleError("bundle.manifest_fields") from error
    return manifest


def _valid_header(block: bytes) -> bool:
    """True if the 512 bytes carry a correct tar header checksum (sum with the checksum field as spaces)."""
    try:
        stored = int(block[148:156].split(b"\0", 1)[0].strip(), 8)
    except ValueError:
        return False
    return stored == sum(block[:148]) + 8 * 32 + sum(block[156:])


def scan_tar(path: Path) -> None:
    """Walk the tar header by header, ourselves, and accept only the exact shape `write_bundle` produces.

    tarfile silently consumes extended headers (PAX `x`/`g`, GNU `L`/`K`) and presents sparse members as
    plain ones, so it cannot be the judge of what lies between the members. Here: exactly two headers,
    `manifest.json` then the pack in any order, both typeflag regular (`0` or NUL), every byte after each
    member's data up to its 512-byte boundary zero, and after the last member only zeros: at least the two
    closing blocks, a multiple of 512 (any record padding of zeros passes). Anything else is refused with
    its own message: cut file (`truncated`), non-plain or hidden members (`bad_member`), names (`bad_layout`),
    non-zero padding (`bad_padding`), bad end (`bad_end`).
    """
    total = path.stat().st_size
    names: list[str] = []
    offset = 0
    with path.open("rb") as raw:
        while True:
            header = raw.read(512)
            if len(header) < 512:
                raise BundleError("bundle.truncated", path=path)
            if header.count(0) == 512:      # first closing block
                break
            if len(names) == 2:             # both members read: a third valid header is one member too many,
                if _valid_header(header):   # anything else non-zero is altered bytes at the end
                    extra = header[:100].split(b"\0", 1)[0].decode("utf-8", "replace")
                    raise BundleError("bundle.bad_layout", path=path,
                                      names=", ".join(ascii(n) for n in [*names, extra]))
                raise BundleError("bundle.bad_end", path=path)
            raw_name, _nul, rest = header[:100].partition(b"\0")
            name = raw_name.decode("utf-8", "replace")
            if rest.count(0) != len(rest):         # bytes hiding after the NUL of the name field
                raise BundleError("bundle.bad_layout", path=path, names=ascii(name))
            if header[156:157] not in (b"0", b"\0"):
                raise BundleError("bundle.bad_member", path=path, name=ascii(name))
            names.append(name)
            if len(names) > 2 or name not in (MANIFEST_NAME, PACK_NAME) or names.count(name) > 1:
                raise BundleError("bundle.bad_layout", path=path, names=", ".join(ascii(n) for n in names[:10]))
            digits = header[124:136].split(b"\0", 1)[0].strip()     # never base-256, signs, underscores or inner spaces
            if not re.fullmatch(rb"[0-7]+", digits) or not _valid_header(header):
                raise BundleError("bundle.unreadable", path=path)
            size = int(digits, 8)
            padded = -(-size // 512) * 512
            if offset + 512 + padded > total:
                raise BundleError("bundle.truncated", path=path)
            raw.seek(offset + 512 + size)
            if padded - size and raw.read(padded - size).count(0) != padded - size:
                raise BundleError("bundle.bad_padding", path=path)
            offset += 512 + padded
            raw.seek(offset)
        if sorted(names) != sorted([MANIFEST_NAME, PACK_NAME]):
            raise BundleError("bundle.bad_layout", path=path, names=", ".join(ascii(n) for n in names) or "-")
        if total < offset + 1024:
            raise BundleError("bundle.truncated", path=path)
        if (total - offset) % 512:
            raise BundleError("bundle.bad_end", path=path)
        raw.seek(offset)
        while chunk := raw.read(CHUNK):
            if chunk.count(0) != len(chunk):
                raise BundleError("bundle.bad_end", path=path)


def open_bundle(path: Path, expected_rev: str, pack_to: Path | None = None) -> Manifest:
    """Validate the tar and return its manifest; copy the pack to `pack_to` when given.

    Checks: readable tar with exactly the two expected regular members, valid manifest,
    commit equal to `expected_rev` (the lockfile), pack size and SHA-256 as declared.
    Nothing is extracted: members are read by name, so no path in the archive is ever used.
    """
    try:
        archive = tarfile.open(path, "r:")
    except FileNotFoundError as error:
        raise BundleError("bundle.not_found", path=path) from error
    except (OSError, tarfile.TarError) as error:
        raise BundleError("bundle.unreadable", path=path) from error
    with archive:
        try:
            scan_tar(path)             # structure first: what tarfile hides (extended headers, sparse) is judged here
            if sorted(m.name for m in archive.getmembers()) != sorted([MANIFEST_NAME, PACK_NAME]):
                raise BundleError("bundle.bad_layout", path=path, names="-")   # tarfile and the scan must agree
            manifest_info = archive.getmember(MANIFEST_NAME)
            if manifest_info.size > MAX_MANIFEST:
                raise BundleError("bundle.manifest_too_large")
            manifest = _parse_manifest(archive.extractfile(manifest_info).read())
            if manifest.rev != expected_rev:
                raise BundleError("bundle.rev_mismatch", got=manifest.rev, want=expected_rev)
            pack_info = archive.getmember(PACK_NAME)
            if pack_info.size != manifest.pack_size:
                raise BundleError("bundle.corrupt", path=path)
            digest, copied = hashlib.sha256(), 0
            source = archive.extractfile(pack_info)
            sink = pack_to.open("wb") if pack_to else None
            try:
                for chunk in iter(lambda: source.read(CHUNK), b""):
                    digest.update(chunk)
                    copied += len(chunk)
                    if sink:
                        sink.write(chunk)
            finally:
                if sink:
                    sink.close()
            if copied != manifest.pack_size or digest.hexdigest() != manifest.pack_sha256:
                if pack_to:
                    pack_to.unlink(missing_ok=True)
                raise BundleError("bundle.corrupt", path=path)
        except tarfile.TarError as error:
            raise BundleError("bundle.unreadable", path=path) from error
    return manifest


def verify_pack_contains(pack: Path, rev: str) -> None:
    """Prove, in a scratch repository outside the toolchain folder, that `pack` holds `rev` and its whole tree."""
    with tempfile.TemporaryDirectory(prefix="glasnost-verify-") as scratch:
        repo = Path(scratch)
        _git(repo, "init", "-q")
        with pack.open("rb") as handle:
            _git(repo, "index-pack", "--stdin", "--fsck-objects", stdin=handle)
        if not has_commit(repo, rev):
            raise BundleError("bundle.commit_missing", want=rev)
        if _git(repo, "rev-list", "--objects", "--no-walk", rev, check=False).returncode != 0:
            raise BundleError("bundle.commit_missing", want=rev)   # a tree or blob is missing


def verify_bundle(path: Path, rev: str) -> Manifest:
    """Everything that can be checked without installing: archive, manifest, hashes, commit and tree."""
    with tempfile.TemporaryDirectory(prefix="glasnost-bundle-") as scratch:
        pack = Path(scratch) / PACK_NAME
        manifest = open_bundle(path, rev, pack_to=pack)
        verify_pack_contains(pack, rev)
    return manifest


def import_pack(checkout: Path, pack: Path, rev: str, origin_url: str | None = None) -> None:
    """Make `checkout` a one-commit shallow repository at `rev`, working tree included.

    `origin_url` becomes the `origin` remote, as `install-toolchain` leaves it after a download.
    """
    checkout.mkdir(parents=True, exist_ok=True)
    if not (checkout / ".git").exists():
        _git(checkout, "init", "-q")
    if origin_url:
        remotes = _git(checkout, "remote").stdout.decode().split()
        _git(checkout, "remote", "set-url" if "origin" in remotes else "add", "origin", origin_url)
    with pack.open("rb") as handle:
        _git(checkout, "index-pack", "--stdin", "--fsck-objects", stdin=handle)
    if not has_commit(checkout, rev):
        raise BundleError("bundle.commit_missing", want=rev)
    shallow = checkout / ".git" / "shallow"
    listed = shallow.read_text(encoding="ascii").split() if shallow.is_file() else []
    if rev not in listed:
        # exclusive temp file and a rename: a planted link at `.git/shallow` is replaced, never written through
        write_text_atomically(shallow, "".join(f"{line}\n" for line in [*listed, rev]))
    _git(checkout, "checkout", "-q", "-f", "--detach", rev)
    head = _git(checkout, "rev-parse", "HEAD").stdout.decode().strip()
    if head != rev:
        raise BundleError("bundle.rev_mismatch", got=head, want=rev)
