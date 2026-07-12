# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Keep this file current.** Whenever you make a change that affects anything
> described here — behavior, commands, architecture, conventions, defaults, file
> layout — update the relevant section of CLAUDE.md (and `README.md` where it
> overlaps) in the same change, so the docs never drift from the code.

## Overview

Ape (`ape-linux` on PyPI) is a CLI that turns a natural-language description of a
Linux task into a shell command using an LLM. The entire implementation lives in a
single module, `ape_linux.py`, exposing two console scripts: `ape` (→ `main()`) and
`ape-system-info` (→ `system_info()`). It has no CLI framework — argument handling is
plain `sys.argv`.

**Single-file rule:** all of Ape's implementation must stay in `ape_linux.py` — do
not split it into additional modules/packages. New behavior is added as functions in
this one file.

## Commands

This project uses [`uv`](https://docs.astral.sh/uv/) for everything, with
[`just`](https://github.com/casey/just) wrapping the CI-relevant tasks.

```bash
just lint                     # lint + format check (ruff check . && ruff format --check .)
just type-check               # type check with ty (uv run ty check)
just test                     # run all tests (uv run pytest)
```

The `justfile` recipes are the single source of truth for lint, type-check, and test:
both local dev and CI (`.github/workflows/tests.yaml`) invoke them, so the two can't
drift. CI installs `just` via the `extractions/setup-just` action. Other useful
commands:

```bash
uv sync                       # install deps + dev group into .venv
uv run pytest tests/test_app.py::test_app_for_version   # run a single test
uv run ruff format .          # format
uv run ape "list all files"   # run the CLI locally
uv build                      # build the wheel/sdist
```

## Architecture

The flow in `ape_linux.py` is intentionally minimal:

1. `main()` is the `ape` entry point. It builds the query by joining `sys.argv[1:]`
   with spaces, so both `ape "list files"` and `ape list files` work. With no
   arguments it prints the `HELP` text and exits with code 1. There are no flags —
   model selection, execution, version, and system-info are all gone. A separate
   `system_info()` function backs the `ape-system-info` console script; it just prints
   `detect_system_context()`.
2. A hard-coded `system_prompt` (with few-shot examples) constrains the model to emit
   a runnable command — no Markdown fences. Rather than a raw string, the agent uses a
   **structured output** union, `Command | CannotHelp` (both `pydantic.BaseModel`s
   defined in `ape_linux.py`): a `Command` carries the shell command in `.command`,
   and a `CannotHelp` carries a short `.reason` for off-topic/unanswerable requests
   (replacing the old `echo "Please try again."` string). This prompt is the core
   product behavior; changes to it directly change what the tool outputs. `main()`
   then appends a system-context block (see below) so suggestions match the current
   machine.
2a. `detect_system_context()` returns a best-effort, newline-separated `Key: value`
   block describing the current machine (OS family + macOS/distro version, whether the
   Linux host is WSL, GNU-vs-BSD userland, CPU arch, `$SHELL`, root-or-not, available
   package managers, and a probed list of common tools). WSL is detected (Linux only)
   from the `WSL_DISTRO_NAME`/`WSL_INTEROP` env vars or `"microsoft"` in
   `platform.uname().release`. Two invariants: it **never raises** (every probe is guarded,
   so an unavailable API or missing file just omits that field instead of crashing at
   startup), and it **never includes identifying info** (no username, hostname, working
   directory, or home path). Everything is stdlib (`platform`, `os`, `shutil.which`) and
   stat-based — no subprocesses — to keep startup fast. Notable guards:
   `platform.freedesktop_os_release()` raises `OSError` on macOS/minimal containers, and
   `os.geteuid()` is absent on non-Unix platforms (`hasattr` check).
3. `call_llm()` wraps `pydantic_ai.Agent`, which is the provider abstraction. It sets
   `output_type=Command | CannotHelp`, so the agent returns one of those structured
   objects instead of raw text (no string-sniffing in `main()`), and forwards a
   `model_settings` mapping (or `None`). Models are passed through verbatim in
   `provider:name` form (e.g. `anthropic:claude-sonnet-4-5`), so Ape supports any
   provider Pydantic AI supports without provider-specific code. The model is resolved
   solely from the `APE_MODEL` env var → the `DEFAULT_MODEL` constant
   (`openai-chat:gpt-4.1`); there is no CLI override. The sampling temperature is
   resolved by `resolve_model_settings()` from the `APE_TEMPERATURE` env var → the
   `DEFAULT_TEMPERATURE` constant (`0.2`); the literal `"undefined"` (case-insensitive)
   yields `None` so **no** `model_settings` are sent — deliberately, because a
   hard-coded temperature crashes models that reject sampling settings (some reasoning
   models, Claude Opus 4.7/4.8) — and an unparseable value exits `1` before any LLM
   call. Credentials come from each provider's standard env var (e.g. `OPENAI_API_KEY`,
   `ANTHROPIC_API_KEY`).
4. Errors are flattened to one-line stderr messages, raising `SystemExit(1)` —
   `ModelHTTPError` reports status/message; any other exception (bad credentials,
   unknown provider) prints `str(error)`. There is no CLI framework swallowing
   tracebacks, so exceptions are caught explicitly. On a successful call, a `Command`
   prints its `.command` to stdout and exits 0, while a `CannotHelp` prints
   `ape: <reason>` to **stderr** and exits `2` — a distinct code so callers can tell
   "can't turn this into a command" apart from operational errors, and stdout stays
   reserved for runnable commands.

## Testing

`tests/test_app.py` drives `main()` directly via a `run()` helper that monkeypatches
`sys.argv` and returns the `SystemExit` code (0 on the success path, since `main()`
doesn't exit then), asserting on captured stdout/stderr with `capsys`. It monkeypatches
`ape_linux.call_llm` so no real network/LLM calls happen; the mock returns a `Command`
(printed to stdout, exit 0) or a `CannotHelp` to exercise the refusal path (printed to
stderr, exit `2`). The `mockenv` fixture sets a dummy `OPENAI_API_KEY`.

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
