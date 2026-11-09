import unittest
from pathlib import Path

from tools.dev.mutate_platformer import MUTATIONS, code_only, spans, strip_comment

ROOT = Path(__file__).resolve().parents[1]


class MutationTableTests(unittest.TestCase):
    """Kept apart from test_ecs_manager: the mutation runner executes that module
    on mutated sources, and this check must not count as a detection."""

    def test_mutation_table_still_matches_the_sources(self):
        sources = [
            (ROOT / "examples/platformer" / name).read_text() for name in ("main.s", "common.inc")
        ]
        names = [name for name, _old, _new in MUTATIONS]
        self.assertEqual(len(names), len(set(names)))
        for name, old, new in MUTATIONS:
            total = sum(len(spans(text, old)) for text in sources)
            self.assertEqual(total, 1, f"mutation {name!r} no longer matches main.s/common.inc once")
            self.assertNotEqual(old, new, name)


class CommentInsensitiveMatching(unittest.TestCase):
    CODE = "    ld a, #1\n    ld (door), a\n    ret\n"

    def test_a_pattern_matches_the_same_code_with_comments_added(self):
        documented = (
            "    ld a, #1            ; door\n"
            "    ;; the door flag\n"
            "\n"
            "    ld (door), a        ; remember it\n"
            "    ret\n")
        self.assertEqual(len(spans(documented, "    ld a, #1\n    ld (door), a")), 1)
        self.assertEqual(len(spans(self.CODE, "    ld a, #1\n    ld (door), a")), 1)

    def test_the_comments_of_the_pattern_are_ignored_too(self):
        self.assertEqual(len(spans(self.CODE, "    ld a, #1   ; old comment\n    ld (door), a")), 1)

    def test_a_code_line_in_between_stops_the_match(self):
        other = "    ld a, #1\n    nop\n    ld (door), a\n"
        self.assertEqual(spans(other, "    ld a, #1\n    ld (door), a"), [])

    def test_a_pattern_ending_in_a_newline_consumes_that_line_and_its_comment(self):
        text = "    inc (hl)   ; tick\n    ret\n"
        (start, end), = spans(text, "    inc (hl)\n")
        self.assertEqual(text[start:end], "    inc (hl)   ; tick\n")

    def test_the_replacement_keeps_the_rest_of_the_file(self):
        text = "    ld a, #1  ; c\n    ld (door), a\n    ret\n"
        (start, end), = spans(text, "    ld a, #1\n    ld (door), a")
        self.assertEqual(text[:start] + "    xor a" + text[end:], "    xor a\n    ret\n")

    def test_semicolons_inside_strings_and_literals_are_not_comments(self):
        self.assertEqual(strip_comment('    .asciz "A;B"   ; why'), '    .asciz "A;B"')
        self.assertEqual(strip_comment("    cp #';'   ; semicolon"), "    cp #';'")

    def test_code_only_drops_comments_and_blank_lines(self):
        self.assertEqual(code_only(";; head\n\n    ld a, b ; x\n  ; y\n    ret\n"), "    ld a, b\n    ret\n")

    def test_a_pattern_without_code_is_rejected(self):
        with self.assertRaises(ValueError):
            spans(self.CODE, "   ; only a comment\n")


if __name__ == "__main__":
    unittest.main()
