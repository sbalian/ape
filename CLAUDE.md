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
   `output_type=[Command, CannotHelp]`, so the agent returns one of those structured
   objects instead of raw text (no string-sniffing in `main()`), and forwards a
   `model_settings` mapping (or `None`). The agent is constructed as
   `Agent[object, Command | CannotHelp](...)` and `output_type` uses Pydantic AI's
   **sequence** form rather than the equivalent `Command | CannotHelp` union: both
   spellings build identical output tools, but ty types a `X | Y` *value* as a
   `types.UnionType` instance, which matches no `Agent.__init__` overload and silently
   degrades the output type to `str`. Written this way, ty and pyright both infer
   `Command | CannotHelp`, so no `ty: ignore` or `cast` on the result is needed —
   keep this spelling. The model string in `provider:name` form
   (e.g. `anthropic:claude-sonnet-4-5`) is turned into a model object via
   `pydantic_ai.models.infer_model()`, to which `call_llm()` passes a custom
   `provider_factory` that builds the inferred provider with
   `infer_provider_class(provider_name)(api_key=api_key)` — i.e. it injects Ape's own
   API key straight into the provider rather than letting Pydantic AI read the
   provider's standard credential env var. This stays provider-agnostic (any provider
   whose class accepts an `api_key` works with no provider-specific code); a provider
   that lacks an `api_key` parameter raises at call time and surfaces as a one-line
   error. `infer_provider_class` is typed as returning `type[Provider[Any]]` and the
   abstract base declares no `__init__`, so the concrete keyword-only `api_key` is
   erased and a cast is unavoidable here. It casts to the `KeyedProviderClass`
   **protocol** rather than `Callable[..., Provider[Any]]` deliberately: the latter
   accepts any arguments at all, so a misspelled keyword would type-check clean. The model is resolved by `resolve_model()` solely from the **required**
   `APE_MODEL` env var (in `provider:name` form); there is no built-in default and no
   CLI override, so the provider is always explicit — a missing/empty `APE_MODEL` exits
   `1` before any LLM call. The API key is resolved by `resolve_api_key()` from the
   **`APE_API_KEY`** env var — Ape's own variable, deliberately *not* a provider's
   standard one (e.g. `OPENAI_API_KEY`), so configuring Ape doesn't force a globally
   named key that other tools also read; a missing/empty `APE_API_KEY` likewise exits
   `1` before any LLM call. The sampling temperature
   is resolved by `resolve_model_settings()` from the `APE_TEMPERATURE` env var → the
   `DEFAULT_TEMPERATURE` constant (`0.2`); the literal `"undefined"` (case-insensitive)
   yields `None` so **no** `model_settings` are sent — deliberately, because a
   hard-coded temperature crashes models that reject sampling settings (some reasoning
   models, Claude Opus 4.7/4.8) — and an unparseable value exits `1` before any LLM
   call. `call_llm()` also sets `PYDANTIC_AI_NO_BANNER=1` in `os.environ` before
   building the agent: recent Pydantic AI versions print a first-run banner (logo plus
   an "observability: off" block) to **stderr** on the first agent run in a terminal,
   which would sit next to Ape's one-line command output. The env var is Pydantic AI's
   documented switch for that — presence alone suppresses it — and is used in
   preference to the equivalent `pydantic_ai.BANNER_ENABLED = False`, which ty infers
   as `Literal[True]` and so cannot be assigned without a `ty: ignore`. Neither needs
   a `pydantic-ai-slim` floor bump: the variable is simply unread on versions that
   predate the banner. Note the banner is invisible to the test suite regardless —
   Pydantic AI suppresses it whenever `PYTEST_VERSION`, `CI` or `PYDANTIC_AI_NO_BANNER`
   is in the environment — so a regression here would only show up when a user runs
   `ape` in a terminal.
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
stderr, exit `2`). The `mockenv` fixture sets a dummy `APE_API_KEY` and `APE_MODEL`
(both required). Tests that assert on `call_llm`'s arguments take its signature
`(model, api_key, system_prompt, user_prompt, model_settings)`; a missing **or
blank/whitespace** `APE_MODEL` or `APE_API_KEY` is each checked to exit `1` before
`call_llm` is ever reached.

`test_call_llm_suppresses_the_pydantic_ai_banner` runs the real `call_llm` (with
`TestModel` swapped in for `infer_model`) and asserts `PYDANTIC_AI_NO_BANNER` ends up
in the environment. It calls `monkeypatch.delenv(..., raising=False)` first, so the
check is meaningful and the environment is restored afterwards.

`build_provider()` is covered directly (not through `main()`): tests construct the
`openai` and `anthropic` providers with the standard credential vars deleted and assert
the injected key lands on `provider.client.api_key` (proving the standard var is neither
needed nor read), and that an unknown provider name raises `ValueError`. Building a
provider is offline, so these make no network calls.

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
  (`.github/workflows/publish.yaml`). See **Releasing** below for the full flow.

## Releasing

Releases are cut from `main` and published to PyPI by the tag-driven `publish.yaml`
workflow, which runs `uv build` + `uv publish` on **any** pushed tag. Tags are **bare
version numbers with no `v` prefix** (e.g. `0.4.6`) and must match `pyproject.toml`'s
`version`. Follow these steps (this is the process that worked for `0.4.6`):

1. **Bump the version** in `pyproject.toml`, then `uv sync` so `uv.lock` records the new
   local package version.
2. **Verify locally**: `just lint`, `just type-check`, and `just test` must all pass.
3. **Branch + commit + push**: create a `release-<version>` branch, commit the change
   (bundle whatever feature work is shipping in the release), and push it.
4. **Open a PR** against `main` (`gh pr create`) and wait for CI to go green with
   `gh pr checks <n> --watch` (the `Tests` workflow runs `Lint` plus the 3.10–3.13 ×
   ubuntu/macos test matrix — nine checks total).
5. **Squash-merge** once green: `gh pr merge <n> --squash --delete-branch`.
6. **Tag on `main`**: `git checkout main && git pull`, then `git tag <version> &&
   git push origin <version>`. Pushing the tag is what triggers `publish.yaml` → PyPI.
7. **Create the GitHub release**: `gh release create <version> --generate-notes
   --verify-tag`. This reuses the already-pushed tag and fills the body with GitHub's
   auto-generated changelog.
8. **Verify the publish**: watch the run (`gh run watch <id> --exit-status`) and confirm
   PyPI serves the new version, e.g. `uv run --isolated --no-project --refresh-package
   ape-linux --with ape-linux python -c "import importlib.metadata as m;
   print(m.version('ape-linux'))"`.

Note on release notes: `--generate-notes` diffs against the previous release tag, so any
PR merged after that tag is listed — including ones that never got their own release.
That is expected, not a bug; leave the auto-generated notes as-is unless asked.
