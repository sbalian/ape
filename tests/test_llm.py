import pytest
from ape import llm


def test_make_user_prompt_injects_query_correctly():
    assert (
        llm.make_user_prompt("Who am I logged in as?")
        == """\
Question: Who am I logged in as?
Answer:"""
    )


def test_make_user_prompt_raises_for_empty_query():
    with pytest.raises(llm.EmptyQueryError):
        llm.make_user_prompt(" ")


def test_no_answer():
    assert llm.no_answer("Please rephrase.")
    assert llm.no_answer("Please Rephrase.")
    assert llm.no_answer("please rephrase.")
    assert llm.no_answer(" Please rephrase.\n")
    assert llm.no_answer("Please rephrase")
    assert llm.no_answer("Please Rephrase")
    assert llm.no_answer("please rephrase")
    assert llm.no_answer(" Please rephrase\n")
    assert not llm.no_answer("ls")


def test_find_answer_returns_suggestion(mockapikey, monkeypatch):
    monkeypatch.setattr("ape.llm.call_llm", lambda *args, **kwargs: "ls")
    assert llm.find_answer("list all the files", "gpt-4o") == "ls"


def test_find_answer_returns_no_suggestion_on_none_from_api(mockapikey, monkeypatch):
    monkeypatch.setattr("ape.llm.call_llm", lambda *args, **kwargs: None)
    assert llm.find_answer("how hot is the sun?", "gpt-4o") == "Please rephrase."
