# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Keep this file current.** Whenever you make a change that affects anything
> described here — behavior, commands, architecture, conventions, defaults, file
> layout — update the relevant section of CLAUDE.md (and `README.md` where it
> overlaps) in the same change, so the docs never drift from the code.

## Overview

Ape (`ape-linux` on PyPI) is a CLI that turns a natural-language description of a
Linux task into a shell command using an LLM. The entire implementation lives in a
single module, `ape_linux.py`, exposing a Typer app as the `ape` console script.

**Single-file rule:** all of Ape's implementation must stay in `ape_linux.py` — do
not split it into additional modules/packages. New behavior is added as functions in
this one file.

## Commands

This project uses [`uv`](https://docs.astral.sh/uv/) for everything.

```bash
uv sync                       # install deps + dev group into .venv
uv run pytest                 # run all tests
uv run pytest tests/test_app.py::test_app_for_version   # run a single test
uv run ruff check .           # lint
uv run ruff format .          # format
uv run ty check               # type check (dev dependency)
uv run ape "list all files"   # run the CLI locally
uv build                      # build the wheel/sdist
```

Note: CI (`.github/workflows/tests.yaml`) currently invokes `uv run pyright .` for
type checking even though `ty` is the declared dev dependency — keep this in mind if
type-check results differ between local and CI.

## Architecture

The flow in `ape_linux.py` is intentionally minimal:

1. `main()` is the single Typer command. It takes the `query` argument plus
   `--model/-m`, `--execute/-e`, `--system-info/-s`, and `--version/-v` options.
   `--system-info` is an eager flag (like `--version`) whose callback prints
   `detect_system_context()` and exits before the LLM is called, so it works without a
   `query`.
2. A hard-coded `system_prompt` (with few-shot examples) constrains the model to emit
   **only** a runnable command — no Markdown fences — or `echo "Please try again."`
   for anything off-topic. This prompt is the core product behavior; changes to it
   directly change what the tool outputs. `main()` then appends a system-context block
   (see below) so suggestions match the current machine.
2a. `detect_system_context()` returns a best-effort, newline-separated `Key: value`
   block describing the current machine (OS family + macOS/distro version, GNU-vs-BSD
   userland, CPU arch, `$SHELL`, root-or-not, available package managers, and a probed
   list of common tools). Two invariants: it **never raises** (every probe is guarded,
   so an unavailable API or missing file just omits that field instead of crashing at
   startup), and it **never includes identifying info** (no username, hostname, working
   directory, or home path). Everything is stdlib (`platform`, `os`, `shutil.which`) and
   stat-based — no subprocesses — to keep startup fast. Notable guards:
   `platform.freedesktop_os_release()` raises `OSError` on macOS/minimal containers, and
   `os.geteuid()` is absent on non-Unix platforms (`hasattr` check).
3. `call_llm()` wraps `pydantic_ai.Agent`, which is the provider abstraction. Models
   are passed through verbatim in `provider:name` form (e.g. `anthropic:claude-sonnet-4-5`),
   so Ape supports any provider Pydantic AI supports without provider-specific code.
   `--model` defaults to `None`; `main()` resolves the model as `--model` (if given)
   → `APE_MODEL` env var → the `DEFAULT_MODEL` constant (`openai-chat:gpt-4.1`).
   Credentials come from each provider's standard env var (e.g. `OPENAI_API_KEY`,
   `ANTHROPIC_API_KEY`).
4. Errors are flattened to one-line stderr messages with exit code 1 —
   `ModelHTTPError` reports status/message; any other exception (bad credentials,
   unknown provider) prints `str(error)`. Tracebacks are suppressed via
   `pretty_exceptions_enable=False` on the Typer app.
5. With `--execute`, the suggested command is run via `subprocess.check_call(..., shell=True)`.

## Testing

`tests/test_app.py` uses `typer.testing.CliRunner` and monkeypatches
`ape_linux.call_llm` so no real network/LLM calls happen. The `mockenv` fixture sets a
dummy `OPENAI_API_KEY`. Note `test_app_for_suggestion_with_execute` mocks the LLM to
return `ls` and actually executes it (harmless, but be aware when adding execute-path
tests — avoid destructive mocked commands).

`detect_system_context()` is covered by tests that assert it returns a string without
crashing, reports the OS, and — importantly — excludes the current username, hostname,
working directory, and home path. These run against the real host (no mocking), so keep
them platform-agnostic; the username check skips the `root` collision with the privilege
line.

## Conventions

- Ruff targets `py314`; lint rules are `F, E, W, I001` (pyflakes, pycodestyle, import
  sorting). `ape_linux` is the known first-party package for import ordering.
- The published package requires Python >=3.10; CI matrixes 3.10–3.13, while local dev
  uses 3.14 (`.python-version`).
- Version is read at runtime from package metadata (`importlib.metadata.version`), so
  the single source of truth is `pyproject.toml`'s `version`. Publishing is tag-driven
  (`.github/workflows/publish.yaml`).
