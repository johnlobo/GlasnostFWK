PYTHON ?= python3
EXAMPLES := minimal board platform gravity physics88 tilecoll tilerender spriteclip spritemask renderorder video resources128 diskload audio animation window vertical perf collision tilemask experimental platformer

.PHONY: all examples test generate report manual platform-guide release clean

all: test

generate:
	$(PYTHON) tools/gen_video.py profiles/standard-160x200.json --out-dir generated
	$(PYTHON) tools/gen_video.py profiles/experimental-160x288.json --out-dir generated
	$(PYTHON) tools/gen_resources.py manifests/resources128.json --output generated/resources128.inc

examples: generate
	$(PYTHON) tools/build_examples.py $(EXAMPLES)
	$(PYTHON) tools/build_test_disk.py $(EXAMPLES)

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
