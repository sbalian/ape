"""AI for Linux commands."""

import os
import platform
import shutil
import subprocess
from importlib.metadata import version
from typing import Annotated

import rich.console
import typer
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

__version__ = version("ape_linux")

DEFAULT_MODEL = "openai-chat:gpt-4.1"

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


def system_info_callback(value: bool) -> None:
    if value:
        typer.echo(detect_system_context())
        raise typer.Exit()


def call_llm(model: str, system_prompt: str, user_prompt: str) -> str | None:
    agent = Agent(
        model,
        system_prompt=system_prompt,
        model_settings={"temperature": 0.2},
    )
    return agent.run_sync(user_prompt).output


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


@app.command()
def main(
    query: Annotated[
        str, typer.Argument(help="Query describing a Linux task.", show_default=False)
    ],
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help=(
                "Model in provider:name form, e.g. anthropic:claude-sonnet-4-5. "
                "See https://ai.pydantic.dev/models/. If unset, the APE_MODEL "
                f"env var is used, falling back to {DEFAULT_MODEL}."
            ),
        ),
    ] = None,
    execute: Annotated[
        bool,
        typer.Option(
            "--execute",
            "-e",
            help="Run the command if suggested. Dangerous!",
        ),
    ] = False,
    system_info: Annotated[
        bool | None,
        typer.Option(
            "--system-info",
            "-s",
            callback=system_info_callback,
            help="Show the detected system context sent to the model, then exit.",
            is_eager=True,
        ),
    ] = None,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            help="Show the version and exit.",
            is_eager=True,
        ),
    ] = None,
):
    """Suggest a command for a Linux task described in QUERY.

    Example: ape "Create a symbolic link named 'win' pointing to /mnt/c/Users/jdoe"

    Output : ln -s /mnt/c/Users/jdoe win
    """

    console = rich.console.Console()

    # An explicit --model wins. Otherwise fall back to APE_MODEL, then the default.
    if model is None:
        model = os.environ.get("APE_MODEL") or DEFAULT_MODEL

    system_prompt = """\
    You are a Linux command assistant. You will be asked a question about how to
    perform a task in Linux or Unix-like operating systems. You should only include
    in your answer the command or commands to perform the task. If you do not know how
    to perform the task, output "echo "Please try again."".

    It is important that you do not output commands enclosed in ``` ``` Markdown
    blocks. For example, do not output:

    ```sh
    cd projects
    ls
    ```

    Instead, your output should be a command that is to be entered directly into the
    command line. For the example above this is: cd projects && ls

    You are also allowed to use \\ for command continuation.

    Here are a few examples.

    Question: List all the files and directories in projects in my home directory
    Answer: ls ~/projects

    Question: Navigate to projects and list its contents
    Answer: cd projects && ls

    Question: What is my username?
    Answer: whoami

    Question: Find all files with the extension .txt under the current working directory
    Answer: find . -name "*.txt"

    Question: What is the captial of France?
    Answer: echo "Please try again."

    Question: Tell me a story
    Answer: echo "Please try again.\""""

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
        with console.status("[bold][blue]Processing ...", spinner="monkey"):
            answer = call_llm(model, system_prompt, user_prompt)
    except ModelHTTPError as error:
        typer.echo(f"{error.status_code} error: {error.message}", err=True)
        raise typer.Exit(1)
    except Exception as error:
        # Anything else (missing/invalid credentials, unknown provider, etc.)
        # surfaces as a one-line message rather than a traceback.
        typer.echo(str(error), err=True)
        raise typer.Exit(1)

    if answer is None:
        answer = 'echo "Please try again."'
    typer.echo(answer)
    if execute:
        subprocess.check_call(answer, shell=True)
