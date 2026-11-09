PYTHON ?= python3

# Without an explicit CPCT_NEXT_PATH, use the toolchain installed by ./setup.sh.
ifeq ($(origin CPCT_NEXT_PATH),undefined)
CPCT_NEXT_PATH := $(shell bin/glasnost path 2>/dev/null)
endif
ifneq ($(CPCT_NEXT_PATH),)
export CPCT_NEXT_PATH
endif
EXAMPLES := minimal board gravity physics88 tilecoll tilerender spriteclip spritemask video resources128 diskload audio window vertical perf tilemask experimental platformer ecsmanager ecscollision ecsanimation ecsrender nave
CHECK_EXAMPLES ?= platformer

.PHONY: all examples check test generate generate-ecs report manual platform-guide release clean

all: test

setup:
	./setup.sh

generate:
	$(PYTHON) tools/build/gen_video.py framework/profiles/standard-160x200.json --out-dir build/generated
	$(PYTHON) tools/build/gen_video.py framework/profiles/experimental-160x288.json --out-dir build/generated
	$(PYTHON) tools/build/gen_resources.py framework/manifests/resources128.json --output build/generated/resources128.inc
	$(PYTHON) tools/build/gen_ecs_profile.py examples/ecsmanager/example.json --output examples/ecsmanager/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py examples/platformer/example.json --output examples/platformer/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py examples/ecscollision/example.json --output examples/ecscollision/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/ecs_collision_model.py --output examples/ecscollision/scenario.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py examples/ecsanimation/example.json --output examples/ecsanimation/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/ecs_animation_model.py --output examples/ecsanimation/scenario.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py examples/ecsrender/example.json --output examples/ecsrender/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/ecs_render_model.py --output examples/ecsrender/scenario.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py examples/nave/example.json --output examples/nave/generated/ecs_profile.inc --check

generate-ecs:
	$(PYTHON) tools/build/gen_ecs_profile.py examples/ecsmanager/example.json --output examples/ecsmanager/generated/ecs_profile.inc

examples: generate
	$(PYTHON) tools/build/build_examples.py $(EXAMPLES)
	$(PYTHON) tools/build/build_test_disk.py $(EXAMPLES)

check: generate
	@test -n "$(strip $(CHECK_EXAMPLES))" || (echo "CHECK_EXAMPLES is required" >&2; exit 2)
	$(PYTHON) -m unittest discover -s tests -q
	$(PYTHON) tools/build/build_examples.py $(CHECK_EXAMPLES)

report: examples
	$(PYTHON) tools/dev/build_report.py

manual:
	$(PYTHON) tools/dev/build_manual.py

platform-guide:
	$(PYTHON) docs/images/platformer/generate_captures.py
	$(PYTHON) tools/dev/build_manual.py --html docs/platform-game-guide.html \
		--pdf docs/platform-game-guide.pdf \
		--checksum docs/platform-game-guide.sha256

release: examples
	@test -n "$(VERSION)" || (echo "VERSION is required (for example: make release VERSION=0.1.0)" >&2; exit 2)
	$(PYTHON) tools/dev/package_release.py --version "$(VERSION)"

test: generate
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) tools/build/build_examples.py $(EXAMPLES)
	$(PYTHON) tools/build/build_test_disk.py $(EXAMPLES)

clean:
	rm -rf build dist
