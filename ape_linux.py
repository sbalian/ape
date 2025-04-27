"""AI for Linux commands."""

import os
import subprocess
from importlib.metadata import version
from typing import Annotated

import openai
import rich.console
import typer

__version__ = version("ape_linux")

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


def call_llm(
    api_key: str, model: str, system_prompt: str, user_prompt: str
) -> str | None:
    return (
        openai.OpenAI(api_key=api_key)
        .chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        .choices[0]
        .message.content
    )


@app.command()
def main(
    query: Annotated[
        str, typer.Argument(help="Query describing a Linux task.", show_default=False)
    ],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="OpenAI model. See https://platform.openai.com/docs/models.",
        ),
    ] = "gpt-4o",
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

    system_prompt = """\
    You are a Linux command assistant. You will be asked a question about how to perform a task in Linux or Unix-like operating systems. You should only include in your answer the command or commands to perform the task. If you do not know how to perform the task, output "echo "Please try again."".

    Here are a few examples.

    Question: List all the files and directories in projects in my home directory
    Answer: ls ~/projects

    Question: What is my username?
    Answer: whoami

    Question: Find all files with the extension .txt under the current working directory
    Answer: find . -name "*.txt"

    Question: What is the captial of France?
    Answer: echo "Please try again."

    Question: Tell me a story
    Answer: echo "Please try again.

    It is important that you do not output commands enclosed in ``` ``` Markdown blocks. For example,

    ```sh
    cd projects
    ls
    ```

    is not allowed. Instead, your output should be a command that is to be entered directly into the command line. For the example above: cd projects && ls

    You are also allowed to use \\ for command continuation.
    \""""  # noqa: E501

    user_prompt = f"""\
    Question: {query.strip()}
    Answer:"""

    try:
        api_key = os.environ["APE_OPENAI_API_KEY"]
    except KeyError:
        typer.echo("Set the environment variable APE_OPENAI_API_KEY.", err=True)
        raise typer.Exit(1)

    try:
        with console.status("[bold][blue]Processing ...", spinner="monkey"):
            answer = call_llm(api_key, model, system_prompt, user_prompt)
            if answer is None:
                answer = 'echo "Please try again."'
        typer.echo(answer)
        if execute:
            subprocess.check_call(answer, shell=True)
    except openai.APIStatusError as error:
        typer.echo(
            f"OpenAI {error.status_code} error: "
            f"{error.response.json()['error']['message']}",
            err=True,
        )
        raise typer.Exit(1)
