import pytest
import typer.testing
from pydantic_ai.exceptions import ModelHTTPError

import ape_linux

runner = typer.testing.CliRunner()


@pytest.fixture
def mockenv(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")


def test_app_for_suggestion(mockenv, monkeypatch):
    monkeypatch.setattr("ape_linux.call_llm", lambda *args, **kwargs: "ls")
    result = runner.invoke(ape_linux.app, ["list all the files"])
    assert result.stdout == "ls\n"
    assert result.stderr == ""
    assert result.exit_code == 0


def test_app_for_try_again_if_api_returns_none(mockenv, monkeypatch):
    monkeypatch.setattr("ape_linux.call_llm", lambda *args, **kwargs: None)
    result = runner.invoke(ape_linux.app, ["what is the capital of England?"])
    assert result.stdout == 'echo "Please try again."\n'
    assert result.stderr == ""
    assert result.exit_code == 0


def test_app_with_api_error(mockenv, monkeypatch):
    def mockreturn(*args, **kwargs):
        raise ModelHTTPError(
            status_code=500, model_name="openai-chat:gpt-4o", body=None
        )

    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    result = runner.invoke(ape_linux.app, ["list all the files"])
    assert result.stdout == ""
    assert result.exit_code == 1


def test_app_with_no_api_key(mockenv, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    result = runner.invoke(ape_linux.app, ["list all the files"])
    assert result.stdout == ""
    assert result.stderr != ""
    assert result.exit_code == 1


def test_app_for_suggestion_with_execute(mockenv, monkeypatch):
    monkeypatch.setattr("ape_linux.call_llm", lambda *args, **kwargs: "ls")
    result = runner.invoke(ape_linux.app, ["list all the files", "--execute"])
    assert result.stdout == "ls\n"  # careful, this will actually run
    assert result.stderr == ""
    assert result.exit_code == 0


def test_app_for_version(mockenv):
    result = runner.invoke(ape_linux.app, ["--version"])
    assert result.stdout == f"{ape_linux.__version__}\n"
    assert result.stderr == ""
    assert result.exit_code == 0
