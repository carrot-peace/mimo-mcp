# Changelog

## v0.3

- Expanded MiMo MCP from one tool into a read-only toolbox: `mimo_ask`, `mimo_summarize`, `mimo_review`, `mimo_test_draft`, and `mimo_compare`.
- Added long-context input policy with optional `MIMO_MAX_INPUT_CHARS` rejection and no truncation.
- Added high-confidence sensitive content blocking before MiMo API calls.
- Added normalized usage reports, max token clamping, stronger API error handling, unit tests, and smoke test.
- Updated Codex config guidance for the v0.3 tool list and environment variables.

## v0.1

- Initial read-only `mimo_ask` MCP tool for MiMo Token Plan.
