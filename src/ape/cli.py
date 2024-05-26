import subprocess
from typing import Annotated

import rich.console
import typer

from ape.llm import (
    ApiKeyUnsetError,
    EmptyQueryError,
    ModelNotFoundError,
    find_answer,
    no_answer,
)

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


@app.command()
def run(
    query: Annotated[str, typer.Argument(help="Query describing a Linux task.")],
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
):
    """Suggest a command for a Linux task described in QUERY.

    Example: ape "Create a symbolic link named 'win' pointing to /mnt/c/Users/jdoe"

    Output : ln -s /mnt/c/Users/jdoe win
    """

    console = rich.console.Console()

    try:
        with console.status("[bold][blue]Processing ...", spinner="monkey"):
            answer = find_answer(query, model)
    except EmptyQueryError:
        typer.echo("Query cannot be empty.", err=True)
        raise typer.Exit(1)
    except ApiKeyUnsetError:
        typer.echo("Please set the OPENAI_API_KEY environment variable.", err=True)
        raise typer.Exit(1)
    except ModelNotFoundError:
        typer.echo(
            f"Model '{model}' not found. See https://platform.openai.com/docs/models.",
            err=True,
        )
        raise typer.Exit(1)

    if no_answer(answer):
        typer.echo(answer, err=True)
        raise typer.Exit(1)

    typer.echo(answer)

    if execute:
        subprocess.check_call(answer, shell=True)
