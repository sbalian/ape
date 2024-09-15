.PHONY: install install-no-lock test type-check lint all

all: install test type-check lint

install:
	poetry install

install-no-lock:
	rm poetry.lock && poetry install

test:
	poetry run pytest

type-check:
	poetry run pyright

lint:
	poetry run ruff check
