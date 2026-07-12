import getpass
import os
import platform
import socket

import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.test import TestModel

import ape_linux


@pytest.fixture
def mockenv(monkeypatch):
    monkeypatch.setenv("APE_API_KEY", "key")
    monkeypatch.setenv("APE_MODEL", "openai:gpt-4.1")


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
    monkeypatch.setattr(
        "ape_linux.call_llm",
        lambda *args, **kwargs: ape_linux.Command(command="ls"),
    )
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == "ls\n"
    assert captured.err == ""
    assert code == 0


def test_app_joins_multiple_args_into_query(mockenv, monkeypatch, capsys):
    captured_prompt = {}

    def mockreturn(model, api_key, system_prompt, user_prompt, model_settings):
        captured_prompt["user"] = user_prompt
        return ape_linux.Command(command="ls")

    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    run(monkeypatch, ["list", "all", "the", "files"])
    assert "list all the files" in captured_prompt["user"]


def test_app_prints_help_and_exits_when_no_args(monkeypatch, capsys):
    code = run(monkeypatch, [])
    captured = capsys.readouterr()
    assert "Usage: ape QUERY" in captured.out
    assert code == 1


def test_app_reports_when_model_cannot_help(mockenv, monkeypatch, capsys):
    monkeypatch.setattr(
        "ape_linux.call_llm",
        lambda *args, **kwargs: ape_linux.CannotHelp(
            reason="I can only help with Linux and Unix command-line tasks."
        ),
    )
    code = run(monkeypatch, ["what is the capital of England?"])
    captured = capsys.readouterr()
    # A refusal never lands on stdout (so it can't be mistaken for a command);
    # it goes to stderr and exits with the dedicated code 2.
    assert captured.out == ""
    assert "I can only help with Linux and Unix command-line tasks." in captured.err
    assert code == 2


def test_app_with_api_error(mockenv, monkeypatch, capsys):
    def mockreturn(*args, **kwargs):
        raise ModelHTTPError(status_code=500, model_name="openai:gpt-4o", body=None)

    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert code == 1


def test_app_with_unexpected_error(mockenv, monkeypatch, capsys):
    # A non-HTTP error (bad credentials, unknown provider, ...) is flattened to a
    # one-line stderr message and exits 1, rather than surfacing a traceback.
    def mockreturn(*args, **kwargs):
        raise RuntimeError("something broke")

    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "something broke" in captured.err
    assert code == 1


def test_app_with_no_api_key(mockenv, monkeypatch, capsys):
    # With APE_API_KEY unset (but APE_MODEL present via mockenv), ape must exit
    # before ever reaching the LLM.
    monkeypatch.delenv("APE_API_KEY", raising=False)
    monkeypatch.setattr(
        "ape_linux.call_llm",
        lambda *args, **kwargs: pytest.fail("call_llm should not be called"),
    )
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "APE_API_KEY" in captured.err
    assert code == 1


def test_app_with_blank_api_key(mockenv, monkeypatch, capsys):
    # A whitespace-only APE_API_KEY is treated as unset: exit before the LLM.
    monkeypatch.setenv("APE_API_KEY", "   ")
    monkeypatch.setattr(
        "ape_linux.call_llm",
        lambda *args, **kwargs: pytest.fail("call_llm should not be called"),
    )
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "APE_API_KEY" in captured.err
    assert code == 1


def test_app_passes_api_key_to_call_llm(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, api_key, *args, **kwargs):
        captured["api_key"] = api_key
        return ape_linux.Command(command="ls")

    monkeypatch.setenv("APE_API_KEY", "secret-key")
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    assert captured["api_key"] == "secret-key"
    assert code == 0


def test_app_with_no_model(mockenv, monkeypatch, capsys):
    # With APE_MODEL unset, ape must exit before ever reaching the LLM.
    monkeypatch.delenv("APE_MODEL", raising=False)
    monkeypatch.setattr(
        "ape_linux.call_llm",
        lambda *args, **kwargs: pytest.fail("call_llm should not be called"),
    )
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "APE_MODEL" in captured.err
    assert code == 1


def test_app_with_blank_model(mockenv, monkeypatch, capsys):
    # A whitespace-only APE_MODEL is treated as unset: exit before the LLM.
    monkeypatch.setenv("APE_MODEL", "   ")
    monkeypatch.setattr(
        "ape_linux.call_llm",
        lambda *args, **kwargs: pytest.fail("call_llm should not be called"),
    )
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "APE_MODEL" in captured.err
    assert code == 1


def test_app_uses_ape_model_env_var(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, *args, **kwargs):
        captured["model"] = model
        return ape_linux.Command(command="ls")

    monkeypatch.setenv("APE_MODEL", "anthropic:claude-sonnet-4-5")
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    assert captured["model"] == "anthropic:claude-sonnet-4-5"
    assert code == 0


def test_app_uses_default_temperature_when_unset(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, api_key, system_prompt, user_prompt, model_settings):
        captured["settings"] = model_settings
        return ape_linux.Command(command="ls")

    monkeypatch.delenv("APE_TEMPERATURE", raising=False)
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    assert captured["settings"] == {"temperature": ape_linux.DEFAULT_TEMPERATURE}
    assert ape_linux.DEFAULT_TEMPERATURE == 0.2
    assert code == 0


def test_app_uses_ape_temperature_env_var(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, api_key, system_prompt, user_prompt, model_settings):
        captured["settings"] = model_settings
        return ape_linux.Command(command="ls")

    monkeypatch.setenv("APE_TEMPERATURE", "0.7")
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    assert captured["settings"] == {"temperature": 0.7}
    assert code == 0


def test_app_undefined_temperature_sends_no_settings(mockenv, monkeypatch):
    captured = {}

    def mockreturn(model, api_key, system_prompt, user_prompt, model_settings):
        captured["settings"] = model_settings
        return ape_linux.Command(command="ls")

    # "undefined" (any case) means: send no model_settings at all.
    monkeypatch.setenv("APE_TEMPERATURE", "Undefined")
    monkeypatch.setattr("ape_linux.call_llm", mockreturn)
    code = run(monkeypatch, ["list all the files"])
    assert captured["settings"] is None
    assert code == 0


def test_app_invalid_temperature_exits_before_llm(mockenv, monkeypatch, capsys):
    monkeypatch.setenv("APE_TEMPERATURE", "hot")
    # An invalid temperature must be caught before any LLM call is attempted.
    monkeypatch.setattr(
        "ape_linux.call_llm",
        lambda *args, **kwargs: pytest.fail("call_llm should not be called"),
    )
    code = run(monkeypatch, ["list all the files"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "APE_TEMPERATURE" in captured.err
    assert code == 1


def test_call_llm_returns_structured_output(monkeypatch):
    # Exercise the real call_llm (normally mocked) without a network call by swapping in
    # Pydantic AI's TestModel, which drives the agent and yields structured output
    # offline. This covers the infer_model/Agent wiring and the output cast.
    monkeypatch.setattr(
        "ape_linux.infer_model", lambda model, provider_factory: TestModel()
    )
    result = ape_linux.call_llm(
        "openai:gpt-4.1", "key", "system", "user", {"temperature": 0.2}
    )
    assert isinstance(result, ape_linux.Command)
    assert isinstance(result.command, str)


def test_build_provider_injects_key_without_standard_env_var(monkeypatch):
    # build_provider constructs the inferred provider with our key injected directly,
    # so the provider's standard credential variable is neither needed nor read.
    # Constructing a provider is offline — no request is made until the agent runs.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    openai_provider = ape_linux.build_provider("openai", "injected-key")
    assert openai_provider.name == "openai"
    assert openai_provider.client.api_key == "injected-key"

    anthropic_provider = ape_linux.build_provider("anthropic", "another-key")
    assert anthropic_provider.name == "anthropic"
    assert anthropic_provider.client.api_key == "another-key"


def test_build_provider_unknown_provider_raises():
    # An unrecognized provider name surfaces as ValueError (which main() flattens to a
    # one-line error), rather than silently building the wrong provider.
    with pytest.raises(ValueError):
        ape_linux.build_provider("not-a-real-provider", "key")


def test_system_info_entry_point(capsys):
    ape_linux.system_info()
    captured = capsys.readouterr()
    assert captured.out == f"{ape_linux.detect_system_context()}\n"


def test_detect_system_context_returns_str_and_never_crashes():
    context = ape_linux.detect_system_context()
    assert isinstance(context, str)


def test_detect_system_context_reports_wsl(monkeypatch):
    # Force the Linux branch and a WSL marker, regardless of the host.
    monkeypatch.setattr(ape_linux.platform, "system", lambda: "Linux")
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    context = ape_linux.detect_system_context()
    assert "WSL: yes" in context


def test_detect_system_context_omits_wsl_when_absent(monkeypatch):
    monkeypatch.setattr(ape_linux.platform, "system", lambda: "Linux")
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    monkeypatch.setattr(
        ape_linux.platform,
        "uname",
        lambda: platform.uname_result(
            "Linux", "host", "5.15.0-generic", "#1", "x86_64"
        ),
    )
    context = ape_linux.detect_system_context()
    assert "WSL:" not in context


def test_detect_system_context_reports_operating_system():
    # platform.system() is non-empty on every supported platform.
    context = ape_linux.detect_system_context()
    assert "Operating system:" in context


def test_detect_system_context_reports_distribution(monkeypatch):
    # On Linux, the distribution name from os-release is reported.
    monkeypatch.setattr(ape_linux.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        ape_linux.platform,
        "freedesktop_os_release",
        lambda: {"PRETTY_NAME": "Ubuntu 22.04.3 LTS"},
    )
    context = ape_linux.detect_system_context()
    assert "Distribution: Ubuntu 22.04.3 LTS" in context


def test_detect_system_context_never_raises_when_probe_fails(monkeypatch):
    # The "never raises" invariant: when a probe raises, that field is omitted and the
    # function still returns a string rather than crashing at startup.
    monkeypatch.setattr(ape_linux.platform, "system", lambda: "Darwin")

    def boom(*args, **kwargs):
        raise OSError("probe failed")

    monkeypatch.setattr(ape_linux.platform, "mac_ver", boom)
    context = ape_linux.detect_system_context()
    assert isinstance(context, str)
    assert "macOS version:" not in context


def test_detect_system_context_reports_root_privileges(monkeypatch):
    # The root branch changes the guidance (sudo not required); its non-root twin is
    # covered by the real host running these tests unprivileged.
    monkeypatch.setattr(ape_linux.os, "geteuid", lambda: 0)
    context = ape_linux.detect_system_context()
    assert "Privileges: root (sudo not required)" in context


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
