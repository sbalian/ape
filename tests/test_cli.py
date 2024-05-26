import os

import typer.testing
from ape import cli, llm

runner = typer.testing.CliRunner(mix_stderr=False)


def test_app_for_suggestion(mocker):
    mocker.patch("ape.llm.call_llm", return_value="ls")
    result = runner.invoke(cli.app, ["list all the files"])
    assert result.stdout == "ls\n"
    assert result.stderr == ""
    assert result.exit_code == 0


def test_app_with_empty_query():
    result = runner.invoke(cli.app, [" "])
    assert result.stdout == ""
    assert result.stderr == "Query cannot be empty.\n"
    assert result.exit_code == 1


def test_app_with_no_api_key(mocker):
    mocker.patch.dict(os.environ, clear=True)
    result = runner.invoke(cli.app, ["list all the files"])
    assert result.stdout == ""
    assert result.stderr.startswith("Generic OpenAI error:")
    assert result.exit_code == 1


def test_app_with_wrong_model(mocker):
    mocker.patch(
        "ape.llm.call_llm",
        side_effect=llm.OpenAIAPIStatusError("model not found", 404),
    )
    result = runner.invoke(cli.app, ["list all the files", "--model", "abcd"])
    assert result.stdout == ""
    assert result.stderr == "OpenAI 404 error: model not found\n"
    assert result.exit_code == 1
