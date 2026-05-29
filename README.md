# MiMo MCP v0.3

Local stdio MCP server for Codex. It exposes a read-only toolbox that sends caller-provided text to the MiMo Token Plan OpenAI-compatible API.

## Tools

- `mimo_ask`: general MiMo prompt with optional context and task type.
- `mimo_summarize`: structured summaries for long code, diffs, or documents.
- `mimo_review`: second opinion focused on risks, edge cases, potential bugs, and missing tests.
- `mimo_test_draft`: test scenarios, boundary cases, pseudocode, or draft tests.
- `mimo_compare`: compare options by complexity, risk, maintainability, and test cost.

All tools only process text arguments passed by the caller. The MCP server does not read project files, write files, execute commands, scan projects, or apply patches.

## Install dependencies

```bash
cd /Users/ptilopsis/Projects/mimo-mcp
python3 -m venv .venv
/Users/ptilopsis/Projects/mimo-mcp/.venv/bin/python -m pip install -r requirements.txt
```

## Environment

The default model is `mimo-v2.5-pro`. The default base URL is `https://token-plan-cn.xiaomimimo.com/v1`.

For fish shell:

```fish
set -Ux MIMO_TP_KEY "tp-..."
set -Ux MIMO_BASE_URL "https://token-plan-cn.xiaomimimo.com/v1"
set -Ux MIMO_DEFAULT_MODEL "mimo-v2.5-pro"
set -Ux MIMO_MAX_INPUT_CHARS 0
```

`MIMO_MAX_INPUT_CHARS=0` means no local character limit. If it is set to a positive integer, tool calls larger than that are rejected instead of being truncated.

Do not put the full key in `config.toml`, this repo, shared shell history, logs, or checked-in files.

## Codex App environment

GUI apps on macOS may not inherit your terminal shell environment. Before starting Codex App, run:

```bash
launchctl setenv MIMO_TP_KEY "tp-..."
launchctl setenv MIMO_BASE_URL "https://token-plan-cn.xiaomimimo.com/v1"
launchctl setenv MIMO_DEFAULT_MODEL "mimo-v2.5-pro"
launchctl setenv MIMO_MAX_INPUT_CHARS "0"
```

Then fully quit and restart Codex App. MCP tool lists are loaded at startup, so config changes may not appear until Codex App is restarted.

To remove values later:

```bash
launchctl unsetenv MIMO_TP_KEY
launchctl unsetenv MIMO_BASE_URL
launchctl unsetenv MIMO_DEFAULT_MODEL
launchctl unsetenv MIMO_MAX_INPUT_CHARS
```

## Codex config

`/Users/ptilopsis/.codex/config.toml` should contain:

```toml
# >>> mimo-mcp
[mcp_servers.mimo]
command = "/Users/ptilopsis/Projects/mimo-mcp/.venv/bin/python"
args = ["/Users/ptilopsis/Projects/mimo-mcp/server.py"]
env_vars = [
  "MIMO_TP_KEY",
  "MIMO_BASE_URL",
  "MIMO_DEFAULT_MODEL",
  "MIMO_MAX_INPUT_CHARS",
]
startup_timeout_sec = 10
tool_timeout_sec = 60
enabled = true
enabled_tools = [
  "mimo_ask",
  "mimo_summarize",
  "mimo_review",
  "mimo_test_draft",
  "mimo_compare",
]
default_tools_approval_mode = "prompt"
# <<< mimo-mcp
```

`default_tools_approval_mode = "prompt"` is intentional: Codex should still show a confirmation prompt before calling MiMo, because tool calls may send caller-provided context to an external API.

## Check in Codex

Restart Codex App, then run:

```text
/mcp
```

Look for the `mimo` MCP server and these tools: `mimo_ask`, `mimo_summarize`, `mimo_review`, `mimo_test_draft`, and `mimo_compare`.

You can explicitly ask Codex to use a tool, for example:

```text
Use mimo_summarize to summarize this diff. Focus on behavior changes.
Use mimo_review for a second opinion on edge cases in this patch.
Use mimo_test_draft to draft pytest scenarios from this context.
Use mimo_compare to compare these two implementation options.
```

## Sensitive content blocking

Before calling MiMo, every tool checks only the text parameters passed to that tool. It does not scan this repository, README, source files, or local project files.

The scanner looks for high-confidence patterns such as `sk-...`, `tp-...`, API key environment variable names, `.env` style secret assignments, private key blocks, Android signing fields, and `key.properties`-like content. Ordinary prose that mentions words like token, key, secret, or password is not blocked by itself.

To test the blocker without calling MiMo:

```text
Use mimo_ask with prompt: "api_key = sk-1234567890abcdef"
```

The tool should return an error listing matched rule categories without echoing the sensitive-looking value.

## Tests

Run unit tests:

```bash
python -m pytest
```

Run the smoke test:

```bash
python scripts/smoke_test.py
```

The smoke test reads `MIMO_TP_KEY` from the environment, sends one short prompt, and prints a short result plus usage report. It skips itself if `MIMO_TP_KEY` is not set and never prints the full key.

## Usage report

Successful tool responses append a usage report with tool name, model, input/output character counts, effective `max_tokens`, clamp status, API token usage when reported, and a non-exact credit multiplier hint for common MiMo models.

## Safety boundary

This server is intentionally narrow:

- read-only helper model access;
- does not read arbitrary local project files;
- does not write user project files;
- does not execute shell commands;
- does not scan projects;
- does not apply patches;
- only processes text passed by the caller;
- reads `MIMO_TP_KEY` only from the environment;
- does not save, print, or write the full API key.

## License

MIT. See [LICENSE](LICENSE).
