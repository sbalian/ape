import openai
import pytest
import typer.testing

from ape_linux import app

runner = typer.testing.CliRunner(mix_stderr=False)


@pytest.fixture
def mockenv(monkeypatch):
    monkeypatch.setenv("APE_OPENAI_API_KEY", "key")


def test_app_for_suggestion(mockenv, monkeypatch):
    monkeypatch.setattr("ape_linux.app.call_llm", lambda *args, **kwargs: "ls")
    result = runner.invoke(app.app, ["list all the files"])
    assert result.stdout == "ls\n"
    assert result.stderr == ""
    assert result.exit_code == 0


def test_app_for_try_again_if_api_returns_none(mockenv, monkeypatch):
    monkeypatch.setattr("ape_linux.app.call_llm", lambda *args, **kwargs: None)
    result = runner.invoke(app.app, ["what is the capital of England?"])
    assert result.stdout == 'echo "Please try again."\n'
    assert result.stderr == ""
    assert result.exit_code == 0


def test_app_with_api_error(mockenv, monkeypatch):
    def mockreturn(*args, **kwargs):
        raise openai.OpenAIError()  # TODO test with openai.APIStatusError

    monkeypatch.setattr("ape_linux.app.call_llm", mockreturn)
    result = runner.invoke(app.app, ["list all the files"])
    assert result.stdout == ""
    assert result.exit_code == 1


def test_app_with_no_api_key(mockenv, monkeypatch):
    monkeypatch.delenv("APE_OPENAI_API_KEY")
    result = runner.invoke(app.app, ["list all the files"])
    assert result.stdout == ""
    assert result.stderr == "Set the environment variable APE_OPENAI_API_KEY.\n"
    assert result.exit_code == 1


def test_app_for_suggestion_with_execute(mockenv, monkeypatch):
    monkeypatch.setattr("ape_linux.app.call_llm", lambda *args, **kwargs: "ls")
    result = runner.invoke(app.app, ["list all the files", "--execute"])
    assert result.stdout == "ls\n"  # careful, this will actually run
    assert result.stderr == ""
    assert result.exit_code == 0
