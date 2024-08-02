import typer.testing
from ape import cli, llm

runner = typer.testing.CliRunner(mix_stderr=False)


def test_app_for_suggestion(monkeypatch):
    monkeypatch.setattr("ape.llm.call_llm", lambda *args, **kwargs: "ls")
    result = runner.invoke(cli.app, ["list all the files"])
    assert result.stdout == "ls\n"
    assert result.stderr == ""
    assert result.exit_code == 0


def test_app_for_try_again(monkeypatch):
    monkeypatch.setattr(
        "ape.llm.call_llm", lambda *args, **kwargs: 'echo "Please try again."'
    )
    result = runner.invoke(cli.app, ["what is the capital of France?"])
    assert result.stdout == 'echo "Please try again."\n'
    assert result.stderr == ""
    assert result.exit_code == 0


def test_app_with_empty_query():
    result = runner.invoke(cli.app, [" "])
    assert result.stdout == ""
    assert result.stderr == "Query cannot be empty.\n"
    assert result.exit_code == 1


def test_app_with_no_model(monkeypatch):
    def mockreturn(*args, **kwargs):
        raise llm.OpenAIAPIStatusError("model not found", 404)

    monkeypatch.setattr("ape.llm.call_llm", mockreturn)
    result = runner.invoke(cli.app, ["list all the files", "--model", "abcd"])
    assert result.stdout == ""
    assert result.stderr == "OpenAI 404 error: model not found\n"
    assert result.exit_code == 1


def test_app_with_no_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.delenv("OPENAI_API_KEY")
    result = runner.invoke(cli.app, ["list all the files"])
    assert result.stdout == ""
    assert result.stderr.startswith("Generic OpenAI error:")
    assert result.exit_code == 1


def test_app_with_wrong_api_key(monkeypatch):
    def mockreturn(*args, **kwargs):
        raise llm.OpenAIAPIStatusError("wrong api key", 401)

    monkeypatch.setattr("ape.llm.call_llm", mockreturn)

    result = runner.invoke(cli.app, ["list all the files"])
    assert result.stdout == ""
    assert result.stderr == "OpenAI 401 error: wrong api key\n"
    assert result.exit_code == 1


def test_app_for_suggestion_with_execute(monkeypatch):
    monkeypatch.setattr("ape.llm.call_llm", lambda *args, **kwargs: "ls")
    result = runner.invoke(cli.app, ["list all the files", "--execute"])
    assert result.stdout == "ls\n"  # careful, this will run!
    assert result.stderr == ""
    assert result.exit_code == 0
