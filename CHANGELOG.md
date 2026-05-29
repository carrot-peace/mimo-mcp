# Changelog

## v0.4.1

- Restricted `MIMO_BASE_URL` to official MiMo Token Plan HTTPS endpoints by default.
- Added explicit opt-in flags for custom HTTPS endpoints and local HTTP development endpoints.
- Rejected unsafe base URL shapes that could leak `MIMO_TP_KEY`, including public HTTP URLs, userinfo, query strings, and fragments.
- Updated README setup guidance for official regions, custom endpoints, local development, and Codex App environment variables.
- Added unit coverage for base URL normalization and rejection behavior.

## v0.4

- Removed the public `max_tokens` parameter from all MCP tools.
- Moved completion budgeting into the MCP server with `max_completion_tokens`.
- Added `budget` modes: `auto`, `default`, and `large`.
- Added configurable default and large completion budgets through `MIMO_DEFAULT_COMPLETION_BUDGET` and `MIMO_LARGE_COMPLETION_BUDGET`.
- Reported budget fallback behavior in tool usage reports.

## v0.3

- Expanded MiMo MCP from one tool into a read-only toolbox: `mimo_ask`, `mimo_summarize`, `mimo_review`, `mimo_test_draft`, and `mimo_compare`.
- Added long-context input policy with optional `MIMO_MAX_INPUT_CHARS` rejection and no truncation.
- Added high-confidence sensitive content blocking before MiMo API calls.
- Added normalized usage reports, max token clamping, stronger API error handling, unit tests, and smoke test.
- Updated Codex config guidance for the v0.3 tool list and environment variables.

## v0.1

- Initial read-only `mimo_ask` MCP tool for MiMo Token Plan.
