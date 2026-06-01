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
ape Create a symbolic link called win pointing to /mnt/c/Users/jdoe
```

Output:

```text
ln -s /mnt/c/Users/jdoe win
```

Another example:

```bash
ape Delete all the .venv directories under projects/
```

Output:

```text
find projects/ -type d -name ".venv" -exec rm -rf {} +
```

If you try to ask something unrelated to Linux commands:

```bash
ape Tell me about monkeys
```

you should get:

```text
echo "Please try again."
```

You can change the model with the `APE_MODEL` environment variable. Models are
specified in `provider:name` form.
See [here](https://ai.pydantic.dev/models/) for the supported providers and models.
For example:

```bash
export APE_MODEL=anthropic:claude-sonnet-4-5
```

If `APE_MODEL` is unset, the default `openai-chat:gpt-4.1` is used.

## System-aware suggestions

Ape automatically detects a few facts about your machine and adds them to the prompt so
the suggested command is correct for *your* environment — for example BSD (macOS) vs GNU
(Linux) flags, the right package manager (`brew`, `apt`, `dnf`, `pacman`, ...), and tools
that are actually installed. It looks at:

- operating system and version (macOS version or Linux distribution),
- whether the userland is BSD or GNU,
- CPU architecture (e.g. `arm64` vs `x86_64`),
- your shell (`$SHELL`),
- whether you are root,
- available package manager(s) and common tools (`rg`, `fd`, `jq`, `docker`, ...).

This is all gathered locally with the Python standard library and is best-effort: if
anything can't be determined it is simply left out. **No identifying information is
collected or sent** — never your username, hostname, working directory, or home path.

To see exactly what Ape detects and sends (without calling the model), run
`ape-system-info`:

```bash
ape-system-info
```

Output (example):

```text
Operating system: Darwin
macOS version: 26.5
Userland: BSD (macOS) — prefer BSD-compatible flags
Architecture: arm64
Shell: /bin/zsh
Privileges: non-root (use sudo for privileged actions)
Package manager(s): brew
Available tools: rg, fd, jq, git, curl, docker, tar, rsync, sed, awk
```

See also: [Gorilla](https://github.com/gorilla-llm)
