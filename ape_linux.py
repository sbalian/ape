"""AI for Linux commands."""

import os
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


def call_llm(model: str, system_prompt: str, user_prompt: str) -> str | None:
    agent = Agent(
        model,
        system_prompt=system_prompt,
        model_settings={"temperature": 0.2},
    )
    return agent.run_sync(user_prompt).output


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
