# Lint with ruff.
lint:
    uv run ruff check .
    uv run ruff format --check .

# Type check with ty.
type-check:
    uv run ty check

# Run the test suite.
test:
    uv run pytest
