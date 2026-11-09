"""`glasnost --help`: every command with its options and a short explanation, in both languages."""

from __future__ import annotations

import argparse
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / d) for d in ("glasnost", "build", "dev")]
sys.path.insert(0, str(ROOT / "tests"))

import glasnost  # noqa: E402
from test_glasnost import run_cli  # noqa: E402


def subcommands(parser):
    return next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction)).choices


def option_actions(command):
    return [a for a in command._actions if a.option_strings and not isinstance(a, glasnost.HelpAction)]


class HelpContent(unittest.TestCase):
    def render(self, lang="es", **env):
        with mock.patch.dict(os.environ, env):
            return glasnost.render_help(glasnost.build_parser(lang), lang)

    def test_every_command_is_in_exactly_one_group(self):
        grouped = [name for _, names in glasnost.HELP_GROUPS for name in names]
        self.assertEqual(sorted(grouped), sorted(subcommands(glasnost.build_parser("es"))))
        self.assertEqual(len(grouped), len(set(grouped)))

    def test_every_command_option_and_its_explanation_is_listed(self):
        for lang in ("es", "en"):
            parser = glasnost.build_parser(lang)
            text = self.render(lang)
            for name, command in subcommands(parser).items():
                block = text[text.index(f"\n  {name} ") + 1:]
                block = re.split(r"\n  \S", block[3:], maxsplit=1)[0] if False else block
                for action in option_actions(command):
                    with self.subTest(lang=lang, command=name, option=action.option_strings[-1]):
                        self.assertIn(action.option_strings[-1], block)
                        words = glasnost.sentence(action.help).split()[:3]
                        self.assertIn(" ".join(words), re.sub(r"\s+", " ", block))

    def test_options_sit_under_their_own_command(self):
        text = self.render("en")
        emulator = text[text.index("\n  emulator "):text.index("\n  toolchains ")]
        for flag in ("--set", "--download", "--reset"):
            self.assertIn(flag, emulator)
        self.assertNotIn("--prefix", emulator)

    def test_each_command_has_a_one_line_explanation(self):
        text = self.render("es")
        for name, summary in {a.dest: a.help for a in next(
                a for a in glasnost.build_parser("es")._actions
                if isinstance(a, argparse._SubParsersAction))._choices_actions}.items():
            self.assertTrue(summary.strip(), name)
            self.assertIn(glasnost.sentence(summary).split()[0], text)

    def test_the_two_languages_differ_and_neither_mixes_in_argparse_english(self):
        spanish, english = self.render("es"), self.render("en")
        self.assertNotEqual(spanish, english)
        for phrase in ("show this help message", "positional arguments", "optional arguments"):
            self.assertNotIn(phrase, spanish)
            self.assertNotIn(phrase, english)
        self.assertIn("Uso:", spanish)
        self.assertIn("Usage:", english)
        self.assertIn("Instalación y diagnóstico", spanish)
        self.assertIn("Setup and diagnostics", english)

    def test_lines_fit_the_terminal_width(self):
        for columns in ("60", "80", "120"):
            text = self.render("es", COLUMNS=columns)
            limit = max(60, min(int(columns), 110))
            for line in text.splitlines():
                self.assertLessEqual(len(line), limit, f"COLUMNS={columns}: {line!r}")

    def test_examples_section_names_real_commands(self):
        text = self.render("es")
        commands = set(subcommands(glasnost.build_parser("es")))
        for command_line, _ in glasnost.HELP_EXAMPLES:
            self.assertIn(command_line.split()[1], commands)
            self.assertIn(command_line, text)

    def test_the_reference_document_named_in_the_footer_exists(self):
        footer = glasnost.say("es", "helptext.footer")
        self.assertTrue((ROOT / re.search(r"(docs/\S+\.md)", footer).group(1)).is_file())


class HelpEntryPoints(unittest.TestCase):
    def test_dash_h_and_double_dash_help_print_the_full_help_and_exit_zero(self):
        for flag in ("--help", "-h"):
            code, out, err = run_cli(["--lang", "en", flag])
            self.assertEqual((code, err), (0, ""), flag)
            self.assertIn("Setup and diagnostics", out)
            self.assertIn("--dry-run", out)

    def test_a_bare_glasnost_shows_the_help_instead_of_a_usage_error(self):
        code, out, err = run_cli(["--lang", "es"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Instalación y diagnóstico", out)

    def test_every_command_has_its_own_help(self):
        for name in subcommands(glasnost.build_parser("en")):
            for argv in ([name, "--help"], ["help", name]):
                with self.subTest(argv):
                    code, out, err = run_cli(["--lang", "en", *argv])
                    self.assertEqual((code, err), (0, ""))
                    self.assertTrue(out.startswith(f"Usage: glasnost {name}"), out[:60])

    def test_command_help_lists_all_its_options(self):
        parser = glasnost.build_parser("en")
        for name, command in subcommands(parser).items():
            _, out, _ = run_cli(["--lang", "en", name, "--help"])
            for action in option_actions(command):
                with self.subTest(name, option=action.option_strings[-1]):
                    self.assertIn(action.option_strings[-1], out)

    def test_usage_shows_mutually_exclusive_options_together(self):
        _, out, _ = run_cli(["--lang", "en", "new", "--help"])
        self.assertIn("[--extended-memory | --no-extended-memory]", re.sub(r"\s+", " ", out))

    def test_help_for_an_unknown_command_is_an_error(self):
        code, _, err = run_cli(["--lang", "en", "help", "frobnicate"])
        self.assertEqual(code, 1)
        self.assertIn("frobnicate", err)

    def test_an_unknown_command_is_still_a_usage_error(self):
        code, _, err = run_cli(["frobnicate"])
        self.assertEqual(code, 2)
        self.assertIn("frobnicate", err)

    def test_parsing_is_unchanged(self):
        parser = glasnost.build_parser("en")
        args = parser.parse_args(["run", "minimal", "--", "--emulator", "x"])
        self.assertEqual((args.command, args.rest), ("run", ["minimal", "--", "--emulator", "x"]))
        args = parser.parse_args(["new", "demo", "--no-extended-memory", "--title", "T"])
        self.assertEqual((args.name, args.extended_memory, args.title), ("demo", False, "T"))


if __name__ == "__main__":
    unittest.main()
