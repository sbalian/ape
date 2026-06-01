"""AI for Linux commands."""

import os
import platform
import shutil
import sys

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

DEFAULT_MODEL = "openai-chat:gpt-4.1"

HELP = """\
ape — AI for Linux commands.

Usage: ape QUERY

Describe a Linux task in QUERY and ape prints a shell command for it.

Example:
    ape "Create a symbolic link named 'win' pointing to /mnt/c/Users/jdoe"
    ln -s /mnt/c/Users/jdoe win

The model is read from the APE_MODEL environment variable in provider:name form
(e.g. anthropic:claude-sonnet-4-5), falling back to {default}. See
https://ai.pydantic.dev/models/. Credentials come from each provider's standard
environment variable (e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY).

Run `ape-system-info` to print the detected system context sent to the model.\
""".format(default=DEFAULT_MODEL)


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

    # The model is read from APE_MODEL, falling back to the default.
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
        answer = call_llm(model, system_prompt, user_prompt)
    except ModelHTTPError as error:
        print(f"{error.status_code} error: {error.message}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as error:
        # Anything else (missing/invalid credentials, unknown provider, etc.)
        # surfaces as a one-line message rather than a traceback.
        print(str(error), file=sys.stderr)
        raise SystemExit(1)

    if answer is None:
        answer = 'echo "Please try again."'
    print(answer)
