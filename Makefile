.PHONY: install demo test pairwise pairwise-select interview arena

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

pairwise-select: install
	$(PYTHON) -m dual_loop_eval.cli pairwise-select

interview: install
	$(PYTHON) -m dual_loop_eval.cli interview

test: install
	$(PYTHON) -m pytest -q

arena: install
	$(PYTHON) -m dual_loop_eval.cli arena
