import getpass
import os
import socket

import pytest
from pydantic_ai.exceptions import ModelHTTPError

import ape_linux


@pytest.fixture
def mockenv(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "key")


def run(monkeypatch, argv):
    """Run ape_linux.main() with the given argv, returning the SystemExit code.

    main() never calls sys.exit() on the success path, so a clean run returns 0.
    """
    monkeypatch.setattr("sys.argv", ["ape", *argv])
    try:
        ape_linux.main()
    except SystemExit as exit:
        return exit.code or 0
    return 0


def test_app_for_suggestion(mockenv, monkeypatch, capsys):
    monkeypatch.setattr("ape_linux.call_llm", lambda *args, **kwargs: "ls")
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == "ls\n"
    assert captured.err == ""
    assert code == 0


def test_app_joins_multiple_args_into_query(mockenv, monkeypatch, capsys):
    captured_prompt = {}

    def mockreturn(model, system_prompt, user_prompt):
        captured_prompt["user"] = user_prompt
        return "ls"

    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    run(monkeypatch, ["list", "all", "the", "files"])
    assert "list all the files" in captured_prompt["user"]


def test_app_prints_help_and_exits_when_no_args(monkeypatch, capsys):
    code = run(monkeypatch, [])
    captured = capsys.readouterr()
    assert "Usage: ape QUERY" in captured.out
    assert code == 1


def test_app_for_try_again_if_api_returns_none(mockenv, monkeypatch, capsys):
    monkeypatch.setattr("ape_linux.call_llm", lambda *args, **kwargs: None)
    code = run(monkeypatch, ["what is the capital of England?"])
    captured = capsys.readouterr()
    assert captured.out == 'echo "Please try again."\n'
    assert captured.err == ""
    assert code == 0


def test_app_with_api_error(mockenv, monkeypatch, capsys):
    def mockreturn(*args, **kwargs):
        raise ModelHTTPError(
            status_code=500, model_name="openai-chat:gpt-4o", body=None
        )

    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert code == 1


def test_app_with_no_api_key(mockenv, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY")
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err != ""
    assert code == 1


def test_app_uses_default_model_when_unset(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, *args, **kwargs):
        captured["model"] = model
        return "ls"

    monkeypatch.delenv("APE_MODEL", raising=False)
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    assert captured["model"] == ape_linux.DEFAULT_MODEL
    assert ape_linux.DEFAULT_MODEL == "openai-chat:gpt-4.1"
    assert code == 0


def test_app_uses_ape_model_env_var(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, *args, **kwargs):
        captured["model"] = model
        return "ls"

    monkeypatch.setenv("APE_MODEL", "anthropic:claude-sonnet-4-5")
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    assert captured["model"] == "anthropic:claude-sonnet-4-5"
    assert code == 0


def test_system_info_entry_point(capsys):
    ape_linux.system_info()
    captured = capsys.readouterr()
    assert captured.out == f"{ape_linux.detect_system_context()}\n"


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
