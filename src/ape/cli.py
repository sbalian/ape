import subprocess
from typing import Annotated

import openai
import rich.console
import typer

from . import llm

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
            answer = llm.find_answer(query, model)
    except llm.EmptyQueryError:
        typer.echo("Query cannot be empty.", err=True)
        raise typer.Exit(1)
    except openai.APIStatusError as e:
        typer.echo(
            f"OpenAI {e.status_code} error: {e.response.json()['error']['message']}",
            err=True,
        )
        raise typer.Exit(1)
    except openai.OpenAIError as e:
        typer.echo(f"OpenAI error: {e}", err=True)
        raise typer.Exit(1)

    if llm.no_answer(answer):
        typer.echo(answer, err=True)
        raise typer.Exit(1)

    typer.echo(answer)

    if execute:
        subprocess.check_call(answer, shell=True)
