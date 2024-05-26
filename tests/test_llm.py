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
    with pytest.raises(ValueError):
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
