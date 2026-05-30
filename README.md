# MiMo MCP

Read-only MiMo Token Plan MCP toolbox for Codex.

[![Tests](https://github.com/carrot-peace/mimo-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/carrot-peace/mimo-mcp/actions/workflows/tests.yml)

Current version: v0.4.1

Local stdio MCP server for Codex. It exposes a read-only toolbox that sends caller-provided text to the MiMo Token Plan OpenAI-compatible API.

## Tools

- `mimo_ask`: general MiMo prompt with optional context and task type.
- `mimo_summarize`: structured summaries for long code, diffs, or documents.
- `mimo_review`: second opinion focused on risks, edge cases, potential bugs, and missing tests.
- `mimo_test_draft`: test scenarios, boundary cases, pseudocode, or draft tests.
- `mimo_compare`: compare options by complexity, risk, maintainability, and test cost.

All tools only process text arguments passed by the caller. The MCP server does not read project files, write files, execute commands, scan projects, or apply patches.

v0.4 introduced server-managed completion budgeting and removed the public `max_tokens` parameter from all tools. Codex should not directly control MiMo output limits with a low `max_tokens` value, because that can silently compress the auxiliary model's answer and make review or summary output less useful. The MCP server now owns completion budgeting and sends `max_completion_tokens` to the OpenAI-compatible API.

v0.4.1 hardened `MIMO_BASE_URL` validation so the server only uses official MiMo Token Plan HTTPS endpoints by default, with explicit opt-in flags for custom HTTPS and local HTTP development endpoints.

Every tool accepts `budget="auto"`, `budget="default"`, or `budget="large"`. The default completion budget is `65536`; the large budget is `131072`. In `auto` mode, long summaries, long or complex reviews, and comparisons can use the large budget. Invalid budget values fall back to `auto` and are reported in the usage report.

## Install dependencies

```bash
cd /Users/ptilopsis/Projects/mimo-mcp
python3 -m venv .venv
/Users/ptilopsis/Projects/mimo-mcp/.venv/bin/python -m pip install -r requirements.txt
```

## Environment

The default model is `mimo-v2.5-pro`. The default base URL is `https://token-plan-cn.xiaomimimo.com/v1`.

By default, `MIMO_BASE_URL` is restricted to official MiMo Token Plan HTTPS endpoints:

- `https://token-plan-cn.xiaomimimo.com/v1`
- `https://token-plan-sgp.xiaomimimo.com/v1`
- `https://token-plan-ams.xiaomimimo.com/v1`

This restriction matters because every API request sends `MIMO_TP_KEY` in the `Authorization` header. If `MIMO_BASE_URL` is misconfigured, polluted, or maliciously redirected to an arbitrary host, the key could be leaked to that host.

To switch official regions, set `MIMO_BASE_URL` to one of the official URLs above. The server accepts `/v1` and `/v1/` and normalizes requests to `/v1/chat/completions`.

Custom HTTPS endpoints are blocked unless explicitly enabled:

```bash
export MIMO_ALLOW_CUSTOM_BASE_URL=1
export MIMO_BASE_URL="https://your-token-plan-compatible-endpoint.example/v1"
```

Custom endpoints still must use `https` and must not include username/password, query strings, or fragments.

Local HTTP is blocked by default. For local development only, you may enable HTTP for `localhost`, `127.0.0.1`, or `::1`:

```bash
export MIMO_ALLOW_INSECURE_LOCAL_HTTP=1
export MIMO_BASE_URL="http://localhost:8080/v1"
```

Public HTTP endpoints are always refused.

For fish shell:

```fish
set -Ux MIMO_TP_KEY "tp-..."
set -Ux MIMO_BASE_URL "https://token-plan-cn.xiaomimimo.com/v1"
set -Ux MIMO_DEFAULT_MODEL "mimo-v2.5-pro"
set -Ux MIMO_MAX_INPUT_CHARS 0
set -Ux MIMO_DEFAULT_COMPLETION_BUDGET 65536
set -Ux MIMO_LARGE_COMPLETION_BUDGET 131072
set -Ux MIMO_ALLOW_CUSTOM_BASE_URL 0
set -Ux MIMO_ALLOW_INSECURE_LOCAL_HTTP 0
```

`MIMO_MAX_INPUT_CHARS=0` means no local character limit. If it is set to a positive integer, tool calls larger than that are rejected instead of being truncated.

If `MIMO_DEFAULT_COMPLETION_BUDGET` or `MIMO_LARGE_COMPLETION_BUDGET` is unset, the defaults above are used. If either value is invalid, the server falls back to the built-in default and reports that fallback in the usage report.

Do not put the full key in `config.toml`, this repo, shared shell history, logs, or checked-in files.

## Codex App environment

GUI apps on macOS may not inherit your terminal shell environment. Before starting Codex App, run:

```bash
launchctl setenv MIMO_TP_KEY "tp-..."
launchctl setenv MIMO_BASE_URL "https://token-plan-cn.xiaomimimo.com/v1"
launchctl setenv MIMO_DEFAULT_MODEL "mimo-v2.5-pro"
launchctl setenv MIMO_MAX_INPUT_CHARS "0"
launchctl setenv MIMO_DEFAULT_COMPLETION_BUDGET "65536"
launchctl setenv MIMO_LARGE_COMPLETION_BUDGET "131072"
launchctl setenv MIMO_ALLOW_CUSTOM_BASE_URL "0"
launchctl setenv MIMO_ALLOW_INSECURE_LOCAL_HTTP "0"
```

Then fully quit and restart Codex App. MCP tool lists and MCP server environment allowlists are loaded at startup, so config or environment changes may not appear until Codex App is restarted.

To remove values later:

```bash
launchctl unsetenv MIMO_TP_KEY
launchctl unsetenv MIMO_BASE_URL
launchctl unsetenv MIMO_DEFAULT_MODEL
launchctl unsetenv MIMO_MAX_INPUT_CHARS
launchctl unsetenv MIMO_DEFAULT_COMPLETION_BUDGET
launchctl unsetenv MIMO_LARGE_COMPLETION_BUDGET
launchctl unsetenv MIMO_ALLOW_CUSTOM_BASE_URL
launchctl unsetenv MIMO_ALLOW_INSECURE_LOCAL_HTTP
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
  "MIMO_DEFAULT_COMPLETION_BUDGET",
  "MIMO_LARGE_COMPLETION_BUDGET",
  "MIMO_ALLOW_CUSTOM_BASE_URL",
  "MIMO_ALLOW_INSECURE_LOCAL_HTTP",
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

Run unit tests with the project virtual environment:

```bash
.venv/bin/python -m pytest
```

Run the smoke test only when you intend to make a real MiMo API call:

```bash
.venv/bin/python scripts/smoke_test.py
```

The smoke test reads `MIMO_TP_KEY` from the environment. If `MIMO_TP_KEY` is not set, it exits cleanly with `SKIP: MIMO_TP_KEY is not set; smoke test did not call MiMo.` and does not call the API. If the key is set, it sends one short prompt to the real MiMo API and prints a short result plus usage report. It never prints the full key.

If you are not using the project virtual environment, install test dependencies first and run an equivalent Python interpreter explicitly.

## Suggested GitHub metadata

Suggested description:

```text
Read-only MiMo Token Plan MCP toolbox for Codex
```

Suggested topics:

```text
mcp
codex
mimo
xiaomi-mimo
llm-tools
python
```

After authenticating `gh`, the repository metadata can be updated with:

```bash
gh repo edit carrot-peace/mimo-mcp \
  --description "Read-only MiMo Token Plan MCP toolbox for Codex" \
  --add-topic mcp \
  --add-topic codex \
  --add-topic mimo \
  --add-topic xiaomi-mimo \
  --add-topic llm-tools \
  --add-topic python
```

## Usage report

Successful tool responses append a usage report with tool name, model, budget mode, completion budget, budget fallback status, input/output character counts, API token usage when reported, and a non-exact credit multiplier hint for common MiMo models.

The actual token counts in the report come only from the MiMo API response `usage` field. If the API response includes usage, the report includes `prompt_tokens`, `completion_tokens`, and `total_tokens` with `usage_source: api_usage`. If the API does not report usage, the server writes `usage_source: not_reported`; in that case input/output character counts are diagnostic only and must not be treated as precise token usage or exact credit consumption.

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
