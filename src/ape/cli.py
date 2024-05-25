from typer import Typer, echo

app = Typer()


@app.command()
def run(query):
    """Suggest a Linux command given QUERY."""
    echo(query)
