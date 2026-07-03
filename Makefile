PYTHON ?= python3

.PHONY: help test

help:
	@echo "Targets:"
	@echo "  make test    — run unit tests"

test:
	@$(PYTHON) -m pytest tests/ -q
