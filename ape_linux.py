"""AI for Linux commands."""

import os
import platform
import shutil
import sys
from functools import partial
from typing import Any, Protocol, cast

from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import infer_model
from pydantic_ai.providers import Provider, infer_provider_class

DEFAULT_TEMPERATURE = 0.2

HELP = """\
ape — AI for Linux commands.

Usage: ape QUERY

Describe a Linux task in QUERY and ape prints a shell command for it.

Example:
    ape "Create a symbolic link named 'win' pointing to /mnt/c/Users/jdoe"
    ln -s /mnt/c/Users/jdoe win

The model is required and read from the APE_MODEL environment variable in
provider:name form (e.g. anthropic:claude-sonnet-4-5). See
https://ai.pydantic.dev/models/. Set your provider API key in APE_API_KEY: Ape
infers the provider from the model name and passes this key straight to it, so
you don't have to set a provider's standard variable (e.g. OPENAI_API_KEY) that
other tools on your system also read.

The sampling temperature is read from APE_TEMPERATURE (default {temperature}). Set
it to "undefined" to send no temperature at all, which some models require.

Run `ape-system-info` to print the detected system context sent to the model.\
""".format(temperature=DEFAULT_TEMPERATURE)


class Command(BaseModel):
    """A shell command (or && / \\-chained commands) for the requested task."""

    command: str


class CannotHelp(BaseModel):
    """A refusal: the request is not a Linux/Unix task that maps to a command."""

    reason: str


class KeyedProviderClass(Protocol):
    """A provider class that can be constructed from an API key alone.

    Every key-based Pydantic AI provider has an ``__init__`` overload taking a
    keyword-only ``api_key``, but ``infer_provider_class`` is typed as returning
    ``type[Provider[Any]]`` and the abstract base declares no ``__init__``, so that
    parameter is erased. ``build_provider`` casts to this protocol to restate it.
    """

    def __call__(self, *, api_key: str) -> Provider[Any]: ...


def build_provider(provider_name: str, api_key: str) -> Provider[Any]:
    """Construct the Pydantic AI provider named by ``provider_name`` with ``api_key``.

    Used (with the key bound via ``functools.partial``) as the ``provider_factory`` for
    ``infer_model`` so Ape injects its own ``APE_API_KEY`` straight into the provider
    rather than letting Pydantic AI read the provider's standard credential env var.
    This stays provider-agnostic: any provider whose class accepts an ``api_key`` works
    without provider-specific code. A provider that lacks an ``api_key`` parameter
    raises at call time (surfaced as a one-line error), which is correct — APE_API_KEY
    only fits key-based providers.
    """
    # infer_provider_class returns the abstract base type[Provider], whose __init__
    # takes no arguments; the concrete `api_key` parameter lives on each subclass and
    # is lost through the return type. No spelling recovers it, so a cast is needed —
    # but it is to KeyedProviderClass rather than `Callable[..., Provider[Any]]`, which
    # would accept *any* arguments and so silently allow a misspelled keyword here.
    provider_class = cast(KeyedProviderClass, infer_provider_class(provider_name))
    return provider_class(api_key=api_key)


def call_llm(
    model: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    model_settings: ModelSettings | None,
) -> Command | CannotHelp:
    # Two spellings here are for the type checker, and neither changes behavior: the
    # generic parameters are explicit (`object` is the default deps type, as Ape uses
    # no deps), and `output_type` uses Pydantic AI's sequence form instead of
    # `Command | CannotHelp`. ty reads a `X | Y` value as a `types.UnionType` instance,
    # which matches neither `type[T]` nor the sequence arm of Pydantic AI's
    # `OutputSpec`, so the union spelling matches no `Agent.__init__` overload and
    # leaves the output typed `str`. The two forms build identical output tools, so
    # the model sees the same schemas.
    agent = Agent[object, Command | CannotHelp](
        # infer_model parses the provider from the `provider:name` prefix;
        # build_provider (with the key bound) constructs it with our APE_API_KEY.
        infer_model(model, provider_factory=partial(build_provider, api_key=api_key)),
        system_prompt=system_prompt,
        output_type=[Command, CannotHelp],
        # None means no settings are sent (see resolve_model_settings), so the model
        # uses its own defaults — needed for models that reject a temperature.
        model_settings=model_settings,
    )
    return agent.run_sync(user_prompt).output


def resolve_model() -> str:
    """Resolve the model from the APE_MODEL environment variable.

    The model is required and given in ``provider:name`` form (e.g.
    ``anthropic:claude-sonnet-4-5``); Ape has no built-in default, so that the
    provider is always explicit (it also determines which API `resolve_api_key`'s key
    is sent to). If unset or empty, the program exits with a one-line error before any
    LLM call.
    """
    model = os.environ.get("APE_MODEL")
    if model is None or not model.strip():
        print(
            "ape: APE_MODEL is not set. Set it to a model in provider:name form, "
            "e.g. anthropic:claude-sonnet-4-5 (run `ape` with no arguments for "
            "details).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return model


def resolve_model_settings() -> ModelSettings | None:
    """Resolve model settings from the APE_TEMPERATURE environment variable.

    Unset (or empty) uses the default temperature. The literal ``"undefined"``
    (case-insensitive) returns ``None`` so that no ``model_settings`` — and thus no
    temperature — is sent to the model; this is what models that reject sampling
    settings (e.g. some reasoning models) need. Any other value must parse as a
    float, otherwise the program exits with a one-line error.
    """
    raw = os.environ.get("APE_TEMPERATURE")
    if raw is None or not raw.strip():
        return {"temperature": DEFAULT_TEMPERATURE}
    value = raw.strip()
    if value.lower() == "undefined":
        return None
    try:
        return {"temperature": float(value)}
    except ValueError:
        print(
            f"ape: invalid APE_TEMPERATURE {value!r}: expected a number or "
            '"undefined".',
            file=sys.stderr,
        )
        raise SystemExit(1)


def resolve_api_key() -> str:
    """Resolve the provider API key from the APE_API_KEY environment variable.

    Ape reads its own ``APE_API_KEY`` rather than each provider's standard variable
    (e.g. ``OPENAI_API_KEY``) so that configuring Ape doesn't force a globally named
    key that other tools on the system also pick up. The key is passed straight to the
    provider inferred from the model name (see ``call_llm``). If it is unset or empty,
    the program exits with a one-line error before any LLM call.
    """
    api_key = os.environ.get("APE_API_KEY")
    if api_key is None or not api_key.strip():
        print(
            "ape: APE_API_KEY is not set. Set it to your provider API key "
            "(run `ape` with no arguments for details).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return api_key


def detect_system_context() -> str:
    """Best-effort description of the current system for the LLM.

    The goal is better, more correct command suggestions for *this* machine
    (e.g. BSD vs GNU flags, the right package manager, tools that exist here).

    Two hard rules:

    1. **Never crash.** This runs on every invocation, so every probe is
       guarded; a failure or a platform that lacks a given API just omits
       that field rather than raising. The worst case is a less-informed
       prompt, never a broken tool at startup.
    2. **Nothing identifying.** No username, hostname, working directory, or
       home path — only facts about the OS and installed tooling.

    Returns a newline-separated block of ``Key: value`` lines (possibly
    empty), suitable for appending to the system prompt.
    """

    lines: list[str] = []

    # OS family. platform.system() always returns a string (possibly empty)
    # and never raises.
    system = platform.system()
    if system:
        lines.append(f"Operating system: {system}")

    if system == "Darwin":
        # mac_ver() returns empty values off-Mac and never raises, but guard
        # defensively anyway.
        try:
            mac_version = platform.mac_ver()[0]
        except Exception:
            mac_version = ""
        if mac_version:
            lines.append(f"macOS version: {mac_version}")
        lines.append("Userland: BSD (macOS) — prefer BSD-compatible flags")
        # GNU coreutils are often installed via Homebrew as g-prefixed tools.
        if shutil.which("gls"):
            lines.append("GNU coreutils also available (gls, gsed, gawk, ...)")
    elif system == "Linux":
        lines.append("Userland: GNU coreutils")
        # freedesktop_os_release() raises OSError when /etc/os-release is
        # absent (e.g. macOS, minimal containers), so it must be guarded.
        try:
            os_release = platform.freedesktop_os_release()
        except Exception:
            os_release = {}
        distribution = os_release.get("PRETTY_NAME") or os_release.get("NAME")
        if distribution:
            lines.append(f"Distribution: {distribution}")

        # WSL (Windows Subsystem for Linux). WSL2 sets WSL_DISTRO_NAME /
        # WSL_INTEROP, and both WSL1 and WSL2 ship a kernel whose release
        # string contains "microsoft" (e.g. 5.15.0-microsoft-standard-WSL2).
        # platform.uname() never raises. This matters because Windows drives
        # are mounted under /mnt and interop tools like clip.exe are available.
        try:
            release = platform.uname().release
        except Exception:
            release = ""
        if (
            os.environ.get("WSL_DISTRO_NAME")
            or os.environ.get("WSL_INTEROP")
            or "microsoft" in release.lower()
        ):
            lines.append(
                "WSL: yes (Windows Subsystem for Linux; "
                "Windows drives under /mnt, interop tools like clip.exe available)"
            )

    # CPU architecture (e.g. arm64 vs x86_64) — affects Homebrew prefixes and
    # binary/platform names. Never raises; may be empty.
    machine = platform.machine()
    if machine:
        lines.append(f"Architecture: {machine}")

    # Interactive shell, which affects available syntax. May be unset.
    shell = os.environ.get("SHELL")
    if shell:
        lines.append(f"Shell: {shell}")

    # Privilege level. os.geteuid() does not exist on non-Unix platforms, so
    # probe for it before calling.
    if hasattr(os, "geteuid"):
        if os.geteuid() == 0:
            lines.append("Privileges: root (sudo not required)")
        else:
            lines.append("Privileges: non-root (use sudo for privileged actions)")

    # Package manager(s). shutil.which() returns None when not found and never
    # raises.
    package_managers = [
        manager
        for manager in ("apt", "dnf", "yum", "pacman", "apk", "zypper", "brew")
        if shutil.which(manager)
    ]
    if package_managers:
        lines.append(f"Package manager(s): {', '.join(package_managers)}")

    # Notable tools that are present, so the model can prefer them (and avoid
    # suggesting ones that are missing).
    candidate_tools = (
        "rg",
        "fd",
        "fzf",
        "jq",
        "yq",
        "git",
        "curl",
        "wget",
        "docker",
        "podman",
        "kubectl",
        "systemctl",
        "tar",
        "rsync",
        "tmux",
        "sed",
        "awk",
    )
    available_tools = [tool for tool in candidate_tools if shutil.which(tool)]
    if available_tools:
        lines.append(f"Available tools: {', '.join(available_tools)}")

    return "\n".join(lines)


def system_info() -> None:
    """Entry point for `ape-system-info`: print the detected system context."""
    print(detect_system_context())


def main() -> None:
    """Entry point for `ape`: suggest a command for the task in the arguments.

    The query is taken from the command-line arguments (``sys.argv``). With no
    arguments, the help text is printed and the program exits non-zero.
    """

    args = sys.argv[1:]
    if not args:
        print(HELP)
        raise SystemExit(1)
    query = " ".join(args)

    # The model is read from APE_MODEL (see resolve_model); a missing model exits
    # here before any LLM call.
    model = resolve_model()

    # The API key is read from APE_API_KEY (see resolve_api_key); a missing key
    # exits here before any LLM call.
    api_key = resolve_api_key()

    # The sampling temperature is read from APE_TEMPERATURE (see
    # resolve_model_settings); an invalid value exits here before any LLM call.
    model_settings = resolve_model_settings()

    system_prompt = """\
    You are a Linux command assistant. You will be asked how to perform a task on
    Linux or a Unix-like operating system. Respond with one of two structured
    outputs:

    - Command: the shell command (or commands) that perform the task, when the
      request is a Linux/Unix task.
    - CannotHelp: a short reason, when the request is not something you can turn into
      a shell command (for example a general-knowledge question or anything
      off-topic).

    For a Command, put something that can be entered directly into the command line
    in the `command` field. Do not wrap it in ``` ``` Markdown code fences. Chain
    multiple steps with && (for example: cd projects && ls) and use \\ for command
    continuation.

    Here are a few examples.

    Question: List all the files and directories in projects in my home directory
    Command: ls ~/projects

    Question: Navigate to projects and list its contents
    Command: cd projects && ls

    Question: What is my username?
    Command: whoami

    Question: Find all files with the extension .txt under the current working directory
    Command: find . -name "*.txt"

    Question: What is the capital of France?
    CannotHelp: I can only help with Linux and Unix command-line tasks.

    Question: Tell me a story
    CannotHelp: I can only help with Linux and Unix command-line tasks."""

    # Append best-effort facts about the current machine so the model can
    # tailor flags, package managers and tool choices to this environment.
    system_context = detect_system_context()
    if system_context:
        system_prompt += (
            "\n\n"
            "Here are details about the current system. Prefer commands that are "
            "correct for this environment (for example BSD vs GNU flags, and the "
            "package manager and tools that are actually available):\n"
            f"{system_context}"
        )

    user_prompt = f"""\
    Question: {query.strip()}
    Answer:"""

    try:
        result = call_llm(model, api_key, system_prompt, user_prompt, model_settings)
    except ModelHTTPError as error:
        print(f"{error.status_code} error: {error.message}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as error:
        # Anything else (missing/invalid credentials, unknown provider, etc.)
        # surfaces as a one-line message rather than a traceback.
        print(str(error), file=sys.stderr)
        raise SystemExit(1)

    # The agent returns a structured result: either a runnable command or a
    # refusal. A refusal goes to stderr and exits 2 (distinct from the code-1
    # operational errors above) so it is never mistaken for a command on stdout.
    if isinstance(result, CannotHelp):
        print(f"ape: {result.reason}", file=sys.stderr)
        raise SystemExit(2)
    print(result.command)
