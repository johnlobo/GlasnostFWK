PYTHON ?= python3
EXAMPLES := minimal board platform video resources128 diskload audio animation window vertical

.PHONY: all examples test generate report manual release clean

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

release: examples
	@test -n "$(VERSION)" || (echo "VERSION is required (for example: make release VERSION=0.1.0)" >&2; exit 2)
	$(PYTHON) tools/package_release.py --version "$(VERSION)"

test: generate
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) tools/build_examples.py $(EXAMPLES)
	$(PYTHON) tools/build_test_disk.py $(EXAMPLES)

clean:
	rm -rf .build dist generated/*.inc generated/*.json generated/*.md
