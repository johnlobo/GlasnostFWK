## GlasnostFWK per-example build entry point.
##
## Included from examples/<name>/Makefile so every consumer can be built on
## its own, the way a standalone CPCtelera project is. The actual project tree
## is still staged in .build/<name>/; after a successful build the BIN, CDT and
## DSK are copied next to the example sources as a convenience. Those copies are
## git-ignored, and `make clean` removes them.
##
## Usage, from examples/<name>/:
##   make          build this example only
##   make run      build and open the resulting image in an emulator
##   make clean    remove .build/<name>/ and the local artifact copies
##   make help     list the targets

GLASNOST_ROOT    ?= $(abspath $(GLASNOST_EXAMPLE_DIR)/../..)
GLASNOST_EXAMPLE ?= $(notdir $(GLASNOST_EXAMPLE_DIR))
GLASNOST_BUILD   := $(GLASNOST_ROOT)/.build/$(GLASNOST_EXAMPLE)

# Artifacts published next to the example sources. The BIN lives in obj/ inside
# the staging tree; CDT and DSK (when the manifest requests them) live at its
# root. Missing files are skipped, so examples without CDT/DSK still work.
GLASNOST_ARTIFACTS := $(GLASNOST_EXAMPLE).bin $(GLASNOST_EXAMPLE).cdt $(GLASNOST_EXAMPLE).dsk

PYTHON ?= python3

# The pinned CPCTelera Next revision is selected with CPCT_NEXT_PATH (or the
# default path inside tools/build_examples.py), exactly like `make examples`
# does. An explicit `make CPCT_PATH=/path` is also honoured; a CPCT_PATH that
# merely comes from the ambient environment is ignored so it cannot silently
# replace the pinned revision.
GLASNOST_CPCT_ARGS := $(if $(filter command line,$(origin CPCT_PATH)),--cpct-path $(CPCT_PATH))

# Optional emulator override, for example:
#   make run GLASNOST_EMULATOR=/path/to/run.sh
GLASNOST_EMULATOR ?=

.PHONY: all build assets run clean help

all: build

build:
	$(PYTHON) $(GLASNOST_ROOT)/tools/build_examples.py $(GLASNOST_EXAMPLE) $(GLASNOST_CPCT_ARGS)
	@for file in $(GLASNOST_ARTIFACTS); do \
		source="$(GLASNOST_BUILD)/obj/$$file"; \
		[ -f "$$source" ] || source="$(GLASNOST_BUILD)/$$file"; \
		if [ -f "$$source" ]; then \
			cp -f "$$source" "$(GLASNOST_EXAMPLE_DIR)/$$file"; \
			echo "  $$file -> examples/$(GLASNOST_EXAMPLE)/$$file"; \
		fi; \
	done

assets:
	$(PYTHON) $(GLASNOST_ROOT)/tools/import_assets.py $(GLASNOST_EXAMPLE) $(GLASNOST_CPCT_ARGS)

run: build
	@GLASNOST_EMULATOR="$(GLASNOST_EMULATOR)" \
		$(PYTHON) $(GLASNOST_ROOT)/tools/run_example.py $(GLASNOST_EXAMPLE)

clean:
	rm -rf $(GLASNOST_BUILD)
	rm -f $(addprefix $(GLASNOST_EXAMPLE_DIR)/,$(GLASNOST_ARTIFACTS))

help:
	@echo "Ejemplo: $(GLASNOST_EXAMPLE)"
	@echo "  make         compila solo este ejemplo y deja BIN/CDT/DSK en su carpeta"
	@echo "  make assets  convierte PNG/TMX solo si cambiaron"
	@echo "  make run     compila y lo abre en el emulador"
	@echo "  make clean   borra $(GLASNOST_BUILD) y las copias locales"
