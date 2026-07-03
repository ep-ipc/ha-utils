REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SCRIPTS := $(REPO_ROOT)/scripts
PYTHON ?= python3

ifneq (,$(wildcard $(REPO_ROOT)/.env))
include $(REPO_ROOT)/.env
export
endif
HA_FONT_SCALE ?= 1
FONT_SCALE ?= $(HA_FONT_SCALE)

.PHONY: help fonts test

help:
	@echo "Targets:"
	@echo "  make fonts   — scale theme typography in ./themes ($(FONT_SCALE)x)"
	@echo "  make test    — run unit tests"

fonts:
	@$(PYTHON) $(SCRIPTS)/scale_theme_fonts.py --apply --scale $(FONT_SCALE)

test:
	@$(PYTHON) -m pytest tests/ -q
