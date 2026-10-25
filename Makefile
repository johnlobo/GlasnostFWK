PYTHON ?= python3
EXAMPLES := minimal board platform video resources128

.PHONY: all examples test generate report clean

all: test

generate:
	$(PYTHON) tools/gen_video.py profiles/standard-160x200.json --out-dir generated
	$(PYTHON) tools/gen_video.py profiles/experimental-160x288.json --out-dir generated
	$(PYTHON) tools/gen_resources.py manifests/resources128.json --output generated/resources128.inc

examples: generate
	$(PYTHON) tools/build_examples.py $(EXAMPLES)

report: examples
	$(PYTHON) tools/build_report.py

test: generate
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) tools/build_examples.py $(EXAMPLES)

clean:
	rm -rf .build generated/*.inc generated/*.json generated/*.md
