import getpass
import os
import socket

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


def test_app_uses_default_model_when_unset(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, *args, **kwargs):
        captured["model"] = model
        return "ls"

    monkeypatch.delenv("APE_MODEL", raising=False)
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    result = runner.invoke(ape_linux.app, ["list all the files"])
    assert captured["model"] == ape_linux.DEFAULT_MODEL
    assert ape_linux.DEFAULT_MODEL == "openai-chat:gpt-4.1"
    assert result.exit_code == 0


def test_app_uses_ape_model_env_var(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, *args, **kwargs):
        captured["model"] = model
        return "ls"

    monkeypatch.setenv("APE_MODEL", "anthropic:claude-sonnet-4-5")
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    result = runner.invoke(ape_linux.app, ["list all the files"])
    assert captured["model"] == "anthropic:claude-sonnet-4-5"
    assert result.exit_code == 0


def test_app_model_option_overrides_env_var(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, *args, **kwargs):
        captured["model"] = model
        return "ls"

    monkeypatch.setenv("APE_MODEL", "anthropic:claude-sonnet-4-5")
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    result = runner.invoke(
        ape_linux.app, ["list all the files", "--model", "groq:llama-3.3-70b"]
    )
    assert captured["model"] == "groq:llama-3.3-70b"
    assert result.exit_code == 0


def test_app_for_version(mockenv):
    result = runner.invoke(ape_linux.app, ["--version"])
    assert result.stdout == f"{ape_linux.__version__}\n"
    assert result.stderr == ""
    assert result.exit_code == 0


def test_app_system_info_flag(mockenv, monkeypatch):
    # The flag must print the context and exit without ever calling the LLM.
    def fail(*args, **kwargs):
        raise AssertionError("call_llm should not be invoked for --system-info")

    monkeypatch.setattr("ape_linux.call_llm", fail)
    result = runner.invoke(ape_linux.app, ["--system-info"])
    assert result.stdout == f"{ape_linux.detect_system_context()}\n"
    assert result.exit_code == 0


def test_detect_system_context_returns_str_and_never_crashes():
    context = ape_linux.detect_system_context()
    assert isinstance(context, str)


def test_detect_system_context_reports_operating_system():
    # platform.system() is non-empty on every supported platform.
    context = ape_linux.detect_system_context()
    assert "Operating system:" in context


def test_detect_system_context_excludes_identifying_info():
    context = ape_linux.detect_system_context()

    # No working directory or home/directory structure.
    assert os.getcwd() not in context
    assert os.path.expanduser("~") not in context

    # No hostname.
    hostname = socket.gethostname()
    if hostname:
        assert hostname not in context

    # No username. ("root" legitimately appears in the privilege line, so
    # skip that unavoidable collision when running as root.)
    username = getpass.getuser()
    if username and username != "root":
        assert username not in context
