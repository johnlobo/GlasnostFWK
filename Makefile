PYTHON ?= python3

# Without an explicit CPCT_NEXT_PATH, use the toolchain installed by ./setup.sh.
ifeq ($(origin CPCT_NEXT_PATH),undefined)
CPCT_NEXT_PATH := $(shell bin/glasnost path 2>/dev/null)
endif
ifneq ($(CPCT_NEXT_PATH),)
export CPCT_NEXT_PATH
endif
EXAMPLES := $(shell $(PYTHON) tools/build/program_catalog.py examples)
VALIDATIONS := $(shell $(PYTHON) tools/build/program_catalog.py validations)
PROGRAMS := $(EXAMPLES) $(VALIDATIONS)
CHECK_EXAMPLES ?= platformer

.PHONY: all examples validations check test generate generate-ecs report manual platform-guide release clean

all: test

setup:
	./setup.sh

generate:
	$(PYTHON) tools/build/gen_video.py framework/profiles/standard-160x200.json --out-dir build/generated
	$(PYTHON) tools/build/gen_video.py framework/profiles/mode1-192x192.json --out-dir build/generated
	$(PYTHON) tools/build/gen_video.py framework/profiles/experimental-160x288.json --out-dir build/generated
	$(PYTHON) tools/build/gen_resources.py framework/manifests/resources128.json --output build/generated/resources128.inc
	$(PYTHON) tools/build/gen_ecs_profile.py framework/validations/ecsmanager/glasnost.manifest.json --output framework/validations/ecsmanager/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py examples/platformer/glasnost.manifest.json --output examples/platformer/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py framework/validations/ecscollision/glasnost.manifest.json --output framework/validations/ecscollision/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/ecs_collision_model.py --output framework/validations/ecscollision/scenario.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py framework/validations/ecsanimation/glasnost.manifest.json --output framework/validations/ecsanimation/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/ecs_animation_model.py --output framework/validations/ecsanimation/scenario.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py framework/validations/ecsrender/glasnost.manifest.json --output framework/validations/ecsrender/generated/ecs_profile.inc --check
	$(PYTHON) tools/build/ecs_render_model.py --output framework/validations/ecsrender/scenario.inc --check
	$(PYTHON) tools/build/gen_ecs_profile.py examples/nave/glasnost.manifest.json --output examples/nave/generated/ecs_profile.inc --check

generate-ecs:
	$(PYTHON) tools/build/gen_ecs_profile.py framework/validations/ecsmanager/glasnost.manifest.json --output framework/validations/ecsmanager/generated/ecs_profile.inc

examples: generate
	$(PYTHON) tools/build/build_examples.py $(EXAMPLES)

validations: generate
	$(PYTHON) tools/build/build_examples.py $(VALIDATIONS)

check: generate
	@test -n "$(strip $(CHECK_EXAMPLES))" || (echo "CHECK_EXAMPLES is required" >&2; exit 2)
	$(PYTHON) -m unittest discover -s tests -q
	$(PYTHON) tools/build/build_examples.py $(CHECK_EXAMPLES)

report: examples validations
	$(PYTHON) tools/dev/build_report.py

manual:
	$(PYTHON) tools/dev/build_manual.py

platform-guide:
	$(PYTHON) docs/guide/images/platformer/generate_captures.py
	$(PYTHON) tools/dev/build_manual.py --html docs/guide/platform-game-guide.html \
		--pdf docs/guide/platform-game-guide.pdf \
		--checksum docs/guide/platform-game-guide.sha256

release: examples validations
	$(PYTHON) tools/build/build_test_disk.py $(PROGRAMS)
	@test -n "$(VERSION)" || (echo "VERSION is required (for example: make release VERSION=0.1.0)" >&2; exit 2)
	$(PYTHON) tools/dev/package_release.py --version "$(VERSION)"

test: generate
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) tools/build/build_examples.py $(PROGRAMS)
	$(PYTHON) tools/build/build_test_disk.py $(PROGRAMS)

clean:
	rm -rf build dist
