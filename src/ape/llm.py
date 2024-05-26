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


class EmptyQueryError(ValueError):
    pass


def make_user_prompt(query: str) -> str:
    query = query.strip()
    if query == "":
        raise EmptyQueryError()
    return USER_PROMPT_TEMPLATE.format(query=query)


def call_llm(user_prompt: str, model: str, system_prompt: str) -> str | None:
    client = openai.OpenAI()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    answer = response.choices[0].message.content
    return answer


def find_answer(query: str, model: str) -> str:
    user_prompt = make_user_prompt(query)

    answer = call_llm(user_prompt, model, SYSTEM_PROMPT)

    if answer is None:
        return "Please rephrase."
    else:
        return answer  # this can also be "Please rephrase."


def no_answer(answer: str) -> bool:
    return answer.strip().lower().rstrip(".") == "please rephrase"
