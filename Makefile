.PHONY: install demo test pairwise

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

install:
	@test -x $(PIP) || python3 -m venv .venv
	$(PIP) install -U pip
	$(PIP) install -e ".[dev]"

demo: install
	$(PYTHON) -m dual_loop_eval.cli demo

pairwise: install
	$(PYTHON) -m dual_loop_eval.cli pairwise-demo

test: install
	$(PYTHON) -m pytest -q
