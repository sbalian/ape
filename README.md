# Ape

Ape is an AI for Linux commands.

```sh
ape "Find all the important PDF files in user/projects. An important PDF file has 'attention' in its name. Write the results to important_files.txt and then move it to Documents."
```

Output:

```text
find ~/user/projects -type f -name "*attention*.pdf" > important_files.txt && mv important_files.txt ~/Documents/
```

Currently, only [OpenAI](https://openai.com/api/) is supported.

To install:

```bash
pipx install ape-linux
```

Next, set your OpenAI API key:

```bash
export APE_OPENAI_API_KEY=key
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

You can change the model using `--model` or `-m`. The default is `gpt-4o`.
See [here](https://platform.openai.com/docs/models) for a list of models. For example:

```bash
ape "List the contents of the working directory with as much detail as possible" --model gpt-3.5-turbo
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
