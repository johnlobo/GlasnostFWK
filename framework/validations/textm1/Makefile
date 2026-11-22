# Standalone build entry point for this example; see framework/cfg/example.mk.
GLASNOST_EXAMPLE_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
GLASNOST_ROOT := $(abspath $(GLASNOST_EXAMPLE_DIR)/../../..)
include $(GLASNOST_EXAMPLE_DIR)/../../cfg/example.mk
