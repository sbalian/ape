# Ape

Ape is an AI for Linux commands.

```sh
ape "List the contents of the working directory one file/directory per line"
```

```text
ls -1
```

You can think of Ape as a lighter version of [Gorilla](https://github.com/gorilla-llm).

Currently, only OpenAI is supported. You will need an API key.

To install:

```bash
pipx install ape-ai
```

Next, set your API key:

```bash
export OPENAI_API_KEY=<key>
```

To run:

```bash
ape "Create a symbolic link called win pointing to /mnt/c/Users/jdoe"
ape "Delete all the .venv directories under projects/"
ape "List the contents of the working directory with as much detail as possible"
ape "Who am I logged in as?"
```

For more options:

```bash
ape --help
```
