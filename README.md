# MiMo MCP v0.1

Local stdio MCP server for Codex. It exposes one read-only tool, `mimo_ask`, which sends caller-provided text to the MiMo Token Plan OpenAI-compatible API.

## Install dependencies

```bash
cd /Users/ptilopsis/Projects/mimo-mcp
python3 -m venv .venv
/Users/ptilopsis/Projects/mimo-mcp/.venv/bin/python -m pip install -r requirements.txt
```

## Set `MIMO_TP_KEY` in fish shell

For the current fish session:

```fish
set -gx MIMO_TP_KEY "your-token-plan-key"
```

Persist it for future fish sessions:

```fish
set -Ux MIMO_TP_KEY "your-token-plan-key"
```

Do not put the key in `config.toml`, this repo, shell history you share, or any checked-in file.

## Set `MIMO_TP_KEY` for Codex App with launchctl

GUI apps on macOS may not inherit your terminal shell environment. Before starting Codex App, run:

```bash
launchctl setenv MIMO_TP_KEY "your-token-plan-key"
```

Then fully quit and reopen Codex App. To remove it later:

```bash
launchctl unsetenv MIMO_TP_KEY
```

## Confirm Codex config was written

Check that `/Users/ptilopsis/.codex/config.toml` contains this block:

```toml
# >>> mimo-mcp
[mcp_servers.mimo]
command = "/Users/ptilopsis/Projects/mimo-mcp/.venv/bin/python"
args = ["/Users/ptilopsis/Projects/mimo-mcp/server.py"]
env_vars = ["MIMO_TP_KEY"]
startup_timeout_sec = 10
tool_timeout_sec = 60
enabled = true
enabled_tools = ["mimo_ask"]
default_tools_approval_mode = "prompt"
# <<< mimo-mcp
```

## Check in Codex TUI

Restart Codex after setting `MIMO_TP_KEY`, then run:

```text
/mcp
```

Look for the `mimo` MCP server and the `mimo_ask` tool.

## Test `mimo_ask`

In Codex, call the MCP tool with a small prompt, for example:

```text
Use mimo_ask with prompt: "用一句话解释 MCP 是什么" and task_type: "explain".
```

If `MIMO_TP_KEY` is missing, the tool returns a clear error telling you to set it. If the MiMo API request fails, the tool returns an HTTP or request error instead of crashing the MCP server.

## Safety boundary

This server is intentionally narrow:

- read-only helper model access;
- does not read local project files;
- does not write files;
- does not execute shell commands;
- only processes text passed by the caller;
- reads `MIMO_TP_KEY` only from the environment;
- does not save, print, or write the API key to any file.

## License

MIT. See [LICENSE](LICENSE).
