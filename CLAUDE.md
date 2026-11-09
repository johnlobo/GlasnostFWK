# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

GlasnostFWK is a modular Z80 assembly framework for the Amstrad CPC, built on a pinned CPCtelera Next (rev in `toolchain.lock.json` and `.github/workflows/ci.yml`; SDCC 4.5.0). Docs, commit messages and CLI output are in Spanish by default. Canonical project state and per-phase history live in `PROJECT_STATUS.md` (update it in every functional/build/release commit).

## Commands

```sh
bin/glasnost doctor              # check tools/toolchain
bin/glasnost install-deps        # system deps (Boost, bison, flex...)
bin/glasnost install-toolchain   # builds pinned CPCtelera into .toolchain/ (gitignored, no sudo)
make generate                    # deterministic generated files (video, resources128, ecs profiles, scenario .inc)
make check                       # fast loop: full host unittest suite + builds only CHECK_EXAMPLES (default: platformer)
make check CHECK_EXAMPLES="spritemask ecsrender"
make test                        # closing gate: host tests + all 23 examples + common test DSK (run once, at commit time)
make manual                      # regenerate docs/manual.pdf from docs/manual.html (needs .venv-docs, see docs/requirements-manual.txt)
make release VERSION=x.y.z       # dist/ ZIP + SHA256SUMS

python3 -m unittest tests.test_sprite -q                          # one test module
python3 -m unittest tests.test_architecture.ArchitectureTests.test_framework_never_imports_examples -v     # one test
python3 tools/build_examples.py platformer                        # build one example into build/<name>/
python3 tests/emulator_smoke.py vertical                          # real AmSpiriT-Lite smoke (optional, needs emulator)
cd examples/minimal && make | make run | make clean              # standalone example build
```

`make generate` runs with `--check` for the ECS profile generators, so a stale generated file fails the build rather than being silently rewritten. After changing a manifest, rerun `make generate` and commit the regenerated `examples/*/generated/ecs_profile.inc` and `scenario.inc`.

Adding an example means updating the `EXAMPLES` list in `Makefile` **and** the two hardcoded example lists in `.github/workflows/ci.yml` (BIN and CDT checks; `diskload` has no CDT).

## Architecture

**Manifest-driven linking.** Each `examples/<name>/example.json` declares `profile`, `modules` (framework sources from `src/`), `game_sources` (consumer files), and optional capabilities (`transparency.pen`, `extended_memory`, ECS layout). `tools/build_examples.py` copies only the declared files into a temporary CPCtelera project under `build/<name>/`; an unselected module is never linked. Absolute paths and `..` in `game_sources` are rejected. The framework is never copied into the repo. Per-example `cfg/build_config.mk` overrides the generated one except for `CPCT_PATH`, `PROJNAME`, `TARGET`, `Z80CODELOC`, `-I$(SRCDIR)`. `assets/assets.json` drives incremental PNG/Tiled conversion (`img2cpc`) and optional ZX7B compression; `examples/platformer` is the reference.

**Dependency direction** (enforced by `tests/test_architecture.py`, e.g. `test_framework_never_imports_examples`): game -> optional extension -> core -> CPCtelera/hardware. Nothing in `src/` may import `examples/` or game symbols. `src/extensions/*` (physics, tilemap, tilemap_render, behavior) are independent and share no universal entity struct.

**ECS 2.0.** Entities live in managers (`src/core/ecs_manager.s`): stable slots, 16-bit component mask, templates, deferred lifecycle. The manager layout is generated from the manifest by `tools/gen_ecs_profile.py`. Systems (`ecs_behavior/motion/input/platform/collision/animation.s`) and the renderer (`src/video/ecs_render.s`) share that layout. Contract: `docs/ecs-abi-2.0.md`; migration plan: `docs/ecs-2.0-master-plan.md`. `ecs_render` splits `prepare` (before VSYNC, no VRAM) from `restore`/`draw` (after VSYNC).

**Python models as oracles.** `tools/ecs_{collision,animation,render}_model.py` mirror the Z80 behavior and generate `scenario.inc` for the matching example; the emulator smoke test checks RAM against the model. Change Z80 behavior and its model together.

**Memory map** (`fwk_project_init` must be called exactly once): transparency table at `0x0100`; code starts at `0x0200`, or `0x0216` with `extended_memory` (stub/scratch in `0x0200..0x0215`). Standard profile is 160x200 Mode 0; `experimental-160x288` is model-verified only, not hardware-verified.

**Tooling layout.** `bin/glasnost` wraps `tools/glasnost.py` (CLI, i18n in `glasnost_i18n.py`); `tools/glasnost_project.py` / `glasnost_update.py` manage generated user projects under `projects/` (gitignored). `templates/` holds `glasnost new` templates.

**Templates and the first-game guide.** `templates/ecs-welcome` ships `assets/` (`assets.json`, `palette.json`, `src/{sprites,tiles}.png`, `src/level.tmx`, committed `assets/generated/`); `render_project` copies `templates/<t>/assets/**` byte for byte, and `minimal` has no ECS, tilemap or assets. Regenerate a template's `assets/generated/` with `tools/import_assets.py` (`convert()`/`check()` take an assets dir; the CLI only takes `examples/<name>`). Nothing checks the carry of framework calls by default: `common.inc` of the template, `docs/first-game/step2|3` and `examples/nave` define `GAME_CHECK_OK` (off, `GAME_DEBUG_CHECKS = 0`, zero cycles) and only the tilemap render call uses it; the docs tell the reader to set `GAME_DEBUG_CHECKS = 1` and place the macro after the calls to guard. `_game_expect_ok` no longer exists. `examples/nave` must equal the overlay of `docs/first-game/step1..3` plus the assets `new` brings (`ExampleMatchesGuide`); step1 only carries `level.tmx`.

## Conventions

- Z80 calling contracts (register in/out, clobbers, preserves) are documented per function in `docs/architecture-and-api.md`; keep them in sync when changing a routine.
- Game projects (`examples/platformer`, `examples/nave`, `projects/*`) put every `.globl`, constant and macro in `common.inc`, imported by every `.s`; `.s` files hold only code and data. Single-file demo examples are not migrated. Enforced for platformer by `test_platformer_follows_the_common_inc_convention`.
- Every new feature must be added to `docs/manual.html`, then `make manual` regenerates the PDF and checksum. `tests/test_manual.py` checks coverage of all examples/modules and PDF sync, so doc-less features fail the suite.
- `tests/test_example_comments.py` and `tests/test_example_targets.py` police example sources and manifests; read them if a new example fails unexpectedly.
- Generated and build outputs (`build/`, `dist/`, `generated/*.inc`, `examples/*/*.{bin,cdt,dsk}`, `.toolchain/`, `projects/`) are gitignored. Never commit binaries.
- `fwk_tilemap_render_view` returns carry and draws nothing for an invalid descriptor: `x_size` is in bytes (2 or 4, with `x_shift` 1 or 2), `y_size` in lines (4 or 8). A 10x6 map at screen (0,0) also covers only a quarter of the screen; the template uses 20x6 at `GAME_MAP_SCREEN_Y`. `sdas` evaluates operators left to right, so split expressions into steps.
- Tests that copy files into a built project must use fresh mtimes (`shutil.copy`, not `copy2`/default `copytree`): `make` compares mtimes, and an older source links the stale object `glasnost new` already built.
- Emulator smokes (optional, `flock /tmp/amspirit.lock python3 tests/<name>.py --emulator /config/workspace/tools/amspirit-lite/run.sh`): `project_smoke.py` (a `glasnost new` project), `first_game_smoke.py` (guide steps, or `--example` for `examples/nave`). Both require the ground row on the last scanline, so a map that silently fails to draw is caught. The `build/nave/obj/nave.bin` reference used by `test_nave_walkthrough` is a stale-able gitignored artifact: rebuild with `python3 tools/build_examples.py nave` if its size test fails after changing `nave`.
- Workflow: one branch per task off `origin/main`, PR, then the session merges its own PR (`gh pr merge N --squash --delete-branch`) once CI ("Host tests and CPC builds") and the local tests for the touched area are green. Never push to `main`.
- `glasnost run` picks its emulator in this order: `--emulator`, `GLASNOST_EMULATOR`, `tools/emulators/emulator.json` (gitignored; written by `glasnost emulator` or the first-run menu), then an interactive one-time menu. Logic and the pinned Retro Virtual Machine downloads (URL, size, SHA-256) live in `tools/emulator_setup.py`, prompts in `tools/glasnost.py` (`ensure_emulator`); without a tty nothing is asked and `run_example.py` keeps auto-detecting. `tests/test_glasnost.py:run_cli` passes `interactive=False` so a terminal never hangs the suite. RVM is launched like CPCtelera's `tools/scripts/cpct_rvm` (`_rvm_command`: `-ns -b=<machine> -i= FILE ...`, literal `\n` in `-c=`), unverified with 2.1.20 and without symbols (no known option); MacAPE and BluePixel get `/A` (dsk) and `/SYM:<name>.noi`; BluePixel (macOS arm64 only) is resolved from the GitHub API's latest release and verified with the asset digest GitHub publishes, and takes `image /A /SYM:` like MacAPE. `default_opener` must send `Accept: application/vnd.github+json` to api.github.com only (any other Accept gets a 415): fakes cannot catch that, so check real endpoints by hand after touching it. Never execute a freshly downloaded emulator in tests: use fake openers (`tests/test_emulator_setup.py`).
- Build, test and doc work needs the toolchain present; CI (`.github/workflows/ci.yml`) caches the pinned CPCtelera build and runs `make test`.
