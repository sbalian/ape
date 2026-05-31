# Ape

Ape is an AI for Linux commands.

```sh
ape "Find all the important PDF files in user/projects. An important PDF file has 'attention' in its name. Write the results to important_files.txt and then move it to Documents."
```

Output:

```text
find ~/user/projects -type f -name "*attention*.pdf" > important_files.txt && mv important_files.txt ~/Documents/
```

Ape works with any provider supported by [Pydantic AI](https://ai.pydantic.dev/models/)
— OpenAI, Anthropic, Google, Groq, Mistral and more.

To install ([`uv`](https://docs.astral.sh/uv/getting-started/installation/) recommended):

```bash
uv tool install ape-linux
```

Next, set the API key for your provider using its standard environment variable.
For example:

```bash
export OPENAI_API_KEY=key      # for OpenAI models
export ANTHROPIC_API_KEY=key   # for Anthropic models
```

To run:

```bash
ape "Create a symbolic link called win pointing to /mnt/c/Users/jdoe"
```

Output:

```text
ln -s /mnt/c/Users/jdoe win
```

Another example:

```bash
ape "Delete all the .venv directories under projects/"
```

Output:

```text
find projects/ -type d -name ".venv" -exec rm -rf {} +
```

If you try to ask something unrelated to Linux commands:

```bash
ape "Tell me about monkeys"
```

you should get:

```text
echo "Please try again."
```

You can change the model using `--model` or `-m`. Models are specified in
`provider:name` form.
See [here](https://ai.pydantic.dev/models/) for the supported providers and models.
For example:

```bash
ape "List the contents of the working directory with as much detail as possible" --model anthropic:claude-sonnet-4-5
```

The model is resolved as follows:

1. If `--model`/`-m` is given, that value is always used.
2. Otherwise, if the `APE_MODEL` environment variable is set, its value is used.
3. Otherwise, the default `openai-chat:gpt-4.1` is used.

So you can set a personal default without passing `--model` every time:

```bash
export APE_MODEL=anthropic:claude-sonnet-4-5
```

Output:

```text
ls -lha
```

If you pass `--execute` or `-e`, the tool will run the command for you after printing it! Be careful with this as LLMs often make mistakes:

```bash
ape "Who am I logged in as?"
```

Output:

```text
whoami
jdoe
```

For more help:

```bash
ape --help
```

See also: [Gorilla](https://github.com/gorilla-llm)
