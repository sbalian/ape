import os

import openai

SYSTEM_PROMPT = """\
You are a Linux command assistant. You will be asked a question about how to perform a task in Linux or Unix-like operating systems. You should only include in your answer the command or commands to perform the task. If you do not know how to perform the task, output "Please rephrase.".

Here are a few examples.

Question: List all the files and directories in projects in my home directory
Answer: ls ~/projects

Question: What is my username?
Answer: whoami

Question: Find all files with the extension .txt under the current working directory
Answer: find . -name "*.txt"

Question: What is the captial of France?
Answer: Please rephrase.

Question: Tell me a story
Answer: Please rephrase."""  # noqa: E501

USER_PROMPT_TEMPLATE = """\
Question: {query}
Answer:"""


class ApiKeyUnsetError(ValueError):
    pass


class EmptyQueryError(ValueError):
    pass


class ModelNotFoundError(ValueError):
    pass


def make_user_prompt(query: str) -> str:
    query = query.strip()
    if query == "":
        raise EmptyQueryError()
    return USER_PROMPT_TEMPLATE.format(query=query)


def find_answer(query: str, model: str) -> str:
    user_prompt = make_user_prompt(query)

    if os.getenv("OPENAI_API_KEY") is None:
        raise ApiKeyUnsetError()

    client = openai.OpenAI()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except openai.NotFoundError:
        raise ModelNotFoundError()

    answer = response.choices[0].message.content
    if answer is None:
        return "Please rephrase."
    else:
        return answer  # this can also be "Please rephrase."


def no_answer(answer: str) -> bool:
    return answer.strip().lower().rstrip(".") == "please rephrase"
