PYTHON ?= python3
VENV ?= .venv

.PHONY: venv install dev test run

venv:
	$(PYTHON) -m venv $(VENV)

install:
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -e .[dev]

dev:
	$(VENV)/bin/uvicorn app.main:app --reload

test:
	$(VENV)/bin/pytest -q
