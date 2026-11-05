PYTHON ?= python3
EXAMPLES := minimal board platform gravity physics88 tilecoll tilerender spriteclip spritemask renderorder video resources128 diskload audio animation window vertical perf collision tilemask experimental platformer ecsmanager ecscollision ecsfuzz platformer_ecs
CHECK_EXAMPLES ?= platformer

.PHONY: all examples check test generate generate-ecs report manual platform-guide release clean

all: test

generate:
	$(PYTHON) tools/gen_video.py profiles/standard-160x200.json --out-dir generated
	$(PYTHON) tools/gen_video.py profiles/experimental-160x288.json --out-dir generated
	$(PYTHON) tools/gen_resources.py manifests/resources128.json --output generated/resources128.inc
	$(PYTHON) tools/gen_ecs_profile.py examples/ecsmanager/example.json --output examples/ecsmanager/generated/ecs_profile.inc --check
	$(PYTHON) tools/gen_ecs_profile.py examples/platformer_ecs/example.json --output examples/platformer_ecs/generated/ecs_profile.inc --check
	$(PYTHON) tools/gen_ecs_profile.py examples/ecscollision/example.json --output examples/ecscollision/generated/ecs_profile.inc --check
	$(PYTHON) tools/gen_ecs_profile.py examples/ecsfuzz/example.json --output examples/ecsfuzz/generated/ecs_profile.inc --check
	$(PYTHON) tools/ecs_collision_model.py --output examples/ecscollision/scenario.inc --check

generate-ecs:
	$(PYTHON) tools/gen_ecs_profile.py examples/ecsmanager/example.json --output examples/ecsmanager/generated/ecs_profile.inc

examples: generate
	$(PYTHON) tools/build_examples.py $(EXAMPLES)
	$(PYTHON) tools/build_test_disk.py $(EXAMPLES)

check: generate
	@test -n "$(strip $(CHECK_EXAMPLES))" || (echo "CHECK_EXAMPLES is required" >&2; exit 2)
	$(PYTHON) -m unittest discover -s tests -q
	$(PYTHON) tools/build_examples.py $(CHECK_EXAMPLES)

report: examples
	$(PYTHON) tools/build_report.py

manual:
	$(PYTHON) tools/build_manual.py

platform-guide:
	$(PYTHON) docs/images/platformer/generate_captures.py
	$(PYTHON) tools/build_manual.py --html docs/platform-game-guide.html \
		--pdf docs/platform-game-guide.pdf \
		--checksum docs/platform-game-guide.sha256

release: examples
	@test -n "$(VERSION)" || (echo "VERSION is required (for example: make release VERSION=0.1.0)" >&2; exit 2)
	$(PYTHON) tools/package_release.py --version "$(VERSION)"

test: generate
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) tools/build_examples.py $(EXAMPLES)
	$(PYTHON) tools/build_test_disk.py $(EXAMPLES)

clean:
	rm -rf .build dist generated/*.inc generated/*.json generated/*.md
