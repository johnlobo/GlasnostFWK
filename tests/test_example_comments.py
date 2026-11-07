"""Gate: every routine the examples call is documented with the project's routine header.

The header, directly above the label (or the `.macro` line):

    ;; ----------------------------------------------------------------------------
    ;; name
    ;;   One or two lines on what it does.
    ;;   In : registers and memory it reads (or "none")
    ;;   Out: registers, flags and memory it leaves (or "none")
    ;;   Clobbers: every register and flag pair it modifies and does not restore, outputs included,
    ;;             and those modified by routines it calls (or "none")
    ;;   Notes: preserved registers, ordering, limits, anything a caller must know
    ;; ----------------------------------------------------------------------------
    name:

Continuation lines start with `;;` and extra indent. The test enforces two things, both
deterministic: every routine has a header, and every header that exists is well formed and
names the label below it. A routine is a label whose next code line is an instruction (not a
directive) and that is entered from outside its own straight-line flow: some `call` targets
it, a `.dw` table or a `#label` operand takes its address (a callback), or it is `_main`.
Loop and branch labels reached only by jr/jp/djnz are local and stay undocumented. Whether the register lists are
TRUE is not machine-checkable here; that is what review is for.

examples/nave is covered: it is the guide's game, kept byte-identical to
docs/first-game/step3 by test_first_game_guide.py, so the guide's final step carries the
headers too. Not covered on purpose: generated or third-party data files, and the
intermediate steps step1 and step2 of the guide.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

SKIP_EXAMPLES: set[str] = set()
SKIP_FILES = {"song.s", "sfx.s", "scenario.inc", "assets.s"}  # generated or pure data

RULE = re.compile(r"^;; -{40,}$")
LABEL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)::?")
MACRO = re.compile(r"^\.macro\s+([A-Za-z_][A-Za-z0-9_]*)")
CALL = re.compile(r"\bcall\s+(?:(?:nz|z|nc|c|po|pe|p|m)\s*,\s*)?#?([A-Za-z_][A-Za-z0-9_]*)")
ADDRESS = re.compile(r"(?:#|\.dw\s+)([A-Za-z_][A-Za-z0-9_]*)")   # `ld hl, #label`, `.dw label`
DIRECTIVE = re.compile(r"^\s*\.[A-Za-z]")
INSTRUCTION = re.compile(r"^\s+[a-z]{2,4}\b")
REQUIRED = ("In :", "Out:", "Clobbers:", "Notes:")   # in this order


def sources() -> list[Path]:
    found = []
    for folder in sorted(EXAMPLES.iterdir()):
        if not folder.is_dir() or folder.name in SKIP_EXAMPLES:
            continue
        for path in sorted(folder.glob("*.s")) + sorted(folder.glob("*.inc")):
            if path.name not in SKIP_FILES:
                found.append(path)
    return found


def read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def declared(line: str) -> str | None:
    match = LABEL.match(line) or MACRO.match(line)
    return match.group(1) if match else None


def is_code_label(lines: list[str], number: int) -> bool:
    """True when the label at `number` is followed (after comments and blanks) by an instruction."""
    if MACRO.match(lines[number]):
        return False
    for line in lines[number + 1:]:
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        return bool(INSTRUCTION.match(line)) and not DIRECTIVE.match(line)
    return False


def headers(lines: list[str]) -> dict[str, list[str]]:
    """name -> header text lines, for every header block closed by a rule and followed by its target."""
    found: dict[str, list[str]] = {}
    index = 0
    while index < len(lines):
        if RULE.match(lines[index]):
            end = index + 1
            while end < len(lines) and not RULE.match(lines[end]):
                end += 1
            if end < len(lines) and end + 1 < len(lines):
                target = declared(lines[end + 1])
                if target is not None:
                    found[target] = lines[index + 1:end]
            index = end + 1
        else:
            index += 1
    return found


class ExampleRoutineHeaders(unittest.TestCase):
    def test_every_routine_has_a_header(self):
        defined: dict[str, Path] = {}
        code: set[str] = set()
        entered: set[str] = {"_main"}
        documented: set[str] = set()
        for path in sources():
            lines = read(path)
            for number, line in enumerate(lines):
                name = declared(line)
                if name is not None:
                    defined.setdefault(name, path)
                    if is_code_label(lines, number):
                        code.add(name)
                text = line.split(";", 1)[0]
                entered.update(CALL.findall(text))
                entered.update(ADDRESS.findall(text))
            documented.update(headers(lines))
        missing = sorted(f"{defined[name].relative_to(ROOT)}: {name}"
                         for name in (entered & code) - documented)
        self.assertEqual(missing, [], f"{len(missing)} routine(s) without a header")

    def test_every_header_is_well_formed_and_names_its_label(self):
        problems = []
        for path in sources():
            lines = read(path)
            for name, body in headers(lines).items():
                where = f"{path.relative_to(ROOT)}: {name}"
                if not body or body[0].strip() != f";; {name}":
                    problems.append(f"{where}: the first line after the rule must be ';; {name}'")
                    continue
                text = "\n".join(body)
                if len(body) < 5:
                    problems.append(f"{where}: needs a description, In, Out, Clobbers and Notes")
                for key in REQUIRED:
                    if not re.search(rf"^;;   {re.escape(key)} \S", text, re.M):
                        problems.append(f"{where}: missing a ';;   {key} ...' line")
                positions = [m.start() for key in REQUIRED
                             if (m := re.search(rf"^;;   {re.escape(key)} \S", text, re.M))]
                if positions != sorted(positions):
                    problems.append(f"{where}: lines must be in the order In, Out, Clobbers, Notes")
                if not re.search(r"^;;   [A-Z]", body[1]):
                    problems.append(f"{where}: the description must follow the name directly")
                if any(not re.match(r"^;;( |$)", line) for line in body):
                    problems.append(f"{where}: every header line must start with ';; '")
        self.assertEqual(problems, [])

    def test_a_header_without_its_label_directly_below_is_reported(self):
        """Self-check of the scanner: a header followed by blank or code is not attached to anything."""
        lines = [";; " + "-" * 76, ";; orphan", ";;   Does things.", ";; " + "-" * 76, "", "orphan:"]
        self.assertEqual(headers(lines), {})
        attached = lines[:4] + ["orphan:"]
        self.assertEqual(list(headers(attached)), ["orphan"])

    def test_code_labels_are_told_from_data_labels(self):
        lines = ["code:", "    ld a, b", "data:", "    .db 1", "gap:", "    ; note", "", "    ret"]
        self.assertEqual([is_code_label(lines, n) for n in (0, 2, 4)], [True, False, True])


if __name__ == "__main__":
    unittest.main()
