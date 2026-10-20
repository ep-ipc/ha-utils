PYTHON ?= python3

PYTHON_HA ?= .venv/bin/python

.PHONY: help test test-ha

help:
	@echo "Targets:"
	@echo "  make test    — run unit tests"
	@echo "  make test-ha — run tests inside Home Assistant (needs requirements_test.txt in .venv)"

test:
	@$(PYTHON) -m pytest tests/ -q

test-ha:
	@$(PYTHON_HA) -m pytest tests_ha/ -q -o asyncio_mode=auto -p no:cacheprovider
