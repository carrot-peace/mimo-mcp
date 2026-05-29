from __future__ import annotations

import asyncio
import inspect
from urllib.parse import urlparse

import pytest

import server


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, text: str = ""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    requests: list[dict] = []
    response = FakeResponse(
        {
            "choices": [{"message": {"content": "MiMo answer"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
    )

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, headers, json):
        self.requests.append({"url": url, "headers": headers, "json": json})
        return self.response


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "MIMO_TP_KEY",
        "MIMO_BASE_URL",
        "MIMO_DEFAULT_MODEL",
        "MIMO_MAX_INPUT_CHARS",
        "MIMO_DEFAULT_COMPLETION_BUDGET",
        "MIMO_LARGE_COMPLETION_BUDGET",
        "MIMO_ALLOW_CUSTOM_BASE_URL",
        "MIMO_ALLOW_INSECURE_LOCAL_HTTP",
    ):
        monkeypatch.delenv(name, raising=False)
    FakeAsyncClient.requests = []
    FakeAsyncClient.response = FakeResponse(
        {
            "choices": [{"message": {"content": "MiMo answer"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
    )
    monkeypatch.setattr(server.httpx, "AsyncClient", FakeAsyncClient)


def run(coro):
    return asyncio.run(coro)


def set_key(monkeypatch):
    monkeypatch.setenv("MIMO_TP_KEY", "test-key-not-a-real-secret")


def assert_refused_without_request(result: str):
    assert result == "Refused: MIMO_BASE_URL is not an approved MiMo endpoint."
    assert FakeAsyncClient.requests == []


def test_missing_mimo_tp_key_returns_clear_error():
    result = run(server.mimo_ask(prompt="hello"))

    assert "MIMO_TP_KEY is not set" in result
    assert FakeAsyncClient.requests == []


@pytest.mark.parametrize(
    "text",
    [
        "Authorization: Bearer tp-1234567890abcdef",
        "api_key = sk-1234567890abcdef",
        "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
        "OPENAI_API_KEY",
        "MIMO_TP_KEY",
        "secret_token = abcdef123456",
        "storePassword=my-store-password",
        "storePassword=aaa\nkeyPassword=bbb\nkeyAlias=release\nstoreFile=release.jks",
    ],
)
def test_sensitive_content_blocks_high_confidence_patterns(monkeypatch, text):
    set_key(monkeypatch)

    result = run(server.mimo_ask(prompt=text))

    assert result.startswith("Error: refused to call MiMo API")
    assert FakeAsyncClient.requests == []


def test_plain_secret_words_do_not_block_without_secret_shape(monkeypatch):
    set_key(monkeypatch)

    result = run(server.mimo_ask(prompt="Please discuss token budgeting and password reset UX at a high level."))

    assert "MiMo answer" in result
    assert len(FakeAsyncClient.requests) == 1


def test_max_input_chars_zero_allows_long_input(monkeypatch):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_MAX_INPUT_CHARS", "0")

    result = run(server.mimo_summarize(context="x" * 10000))

    assert "MiMo answer" in result
    assert len(FakeAsyncClient.requests) == 1


def test_max_input_chars_rejects_when_exceeded(monkeypatch):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_MAX_INPUT_CHARS", "10")

    result = run(server.mimo_summarize(context="x" * 11))

    assert "exceeding MIMO_MAX_INPUT_CHARS=10" in result
    assert FakeAsyncClient.requests == []


def test_all_tool_signatures_hide_max_tokens():
    for name in ("mimo_ask", "mimo_summarize", "mimo_review", "mimo_test_draft", "mimo_compare"):
        signature = inspect.signature(getattr(server, name))
        assert "max_tokens" not in signature.parameters
        assert "budget" in signature.parameters


def test_budget_default_uses_default_completion_budget(monkeypatch):
    set_key(monkeypatch)

    result = run(server.mimo_ask(prompt="hello", budget="default"))

    assert "- budget_mode: default" in result
    assert "- completion_budget: 65536" in result
    assert FakeAsyncClient.requests[0]["json"]["max_completion_tokens"] == 65536
    assert "max_tokens" not in FakeAsyncClient.requests[0]["json"]


def test_budget_large_uses_large_completion_budget(monkeypatch):
    set_key(monkeypatch)

    result = run(server.mimo_ask(prompt="hello", budget="large"))

    assert "- budget_mode: large" in result
    assert "- completion_budget: 131072" in result
    assert FakeAsyncClient.requests[0]["json"]["max_completion_tokens"] == 131072


def test_budget_auto_compare_uses_large(monkeypatch):
    set_key(monkeypatch)

    result = run(server.mimo_compare(options="A vs B"))

    assert "- budget_mode: auto" in result
    assert "- completion_budget: 131072" in result
    assert FakeAsyncClient.requests[0]["json"]["max_completion_tokens"] == 131072


def test_invalid_budget_falls_back_to_auto_and_reports(monkeypatch):
    set_key(monkeypatch)

    result = run(server.mimo_ask(prompt="hello", budget="tiny"))

    assert "- budget_mode: auto" in result
    assert "- completion_budget: 65536" in result
    assert "- budget_fallback_used: true" in result
    assert FakeAsyncClient.requests[0]["json"]["max_completion_tokens"] == 65536


def test_invalid_budget_env_falls_back_to_defaults_and_reports(monkeypatch):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_LARGE_COMPLETION_BUDGET", "not-an-int")

    result = run(server.mimo_compare(options="A vs B"))

    assert "- completion_budget: 131072" in result
    assert "- env_budget_fallback_used: true" in result
    assert "- env_budget_fallbacks: MIMO_LARGE_COMPLETION_BUDGET=invalid" in result


def test_usage_report_contains_required_fields(monkeypatch):
    set_key(monkeypatch)

    result = run(server.mimo_compare(options="A vs B", model="mimo-v2.5"))

    assert "- tool: mimo_compare" in result
    assert "- model: mimo-v2.5" in result
    assert "- input_chars: 6" in result
    assert "- output_chars: 11" in result
    assert "- prompt_tokens: 10" in result
    assert "- completion_tokens: 2" in result
    assert "- total_tokens: 12" in result
    assert "- usage_source: api_usage" in result


def test_usage_report_handles_missing_api_usage(monkeypatch):
    set_key(monkeypatch)
    FakeAsyncClient.response = FakeResponse({"choices": [{"message": {"content": "No usage answer"}}]})

    result = run(server.mimo_test_draft(context="function add(a, b) returns a + b"))

    assert "- tool: mimo_test_draft" in result
    assert "- output_chars: 15" in result
    assert "- usage_source: not_reported" in result
    assert "prompt_tokens" not in result


def test_default_model_and_base_url_from_env(monkeypatch):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_DEFAULT_MODEL", "mimo-v2.5")
    monkeypatch.setenv("MIMO_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("MIMO_ALLOW_CUSTOM_BASE_URL", "1")

    result = run(server.mimo_review(context="review this"))

    assert "- model: mimo-v2.5" in result
    assert FakeAsyncClient.requests[0]["url"] == "https://example.test/v1/chat/completions"
    assert FakeAsyncClient.requests[0]["json"]["model"] == "mimo-v2.5"


@pytest.mark.parametrize(
    ("base_url", "expected_url"),
    [
        ("https://token-plan-cn.xiaomimimo.com/v1", "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"),
        ("https://token-plan-sgp.xiaomimimo.com/v1", "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"),
        ("https://token-plan-ams.xiaomimimo.com/v1", "https://token-plan-ams.xiaomimimo.com/v1/chat/completions"),
        ("https://token-plan-cn.xiaomimimo.com/v1/", "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"),
    ],
)
def test_official_base_urls_are_allowed_and_normalized(monkeypatch, base_url, expected_url):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_BASE_URL", base_url)

    result = run(server.mimo_ask(prompt="hello"))

    assert "MiMo answer" in result
    assert FakeAsyncClient.requests[0]["url"] == expected_url
    assert "//chat/completions" not in FakeAsyncClient.requests[0]["url"]


@pytest.mark.parametrize(
    "base_url",
    [
        "https://evil.example/v1",
        "https://token-plan-cn.xiaomimimo.com.evil.com/v1",
        "https://token-plan-cn.xiaomimimo.com:443/v1",
        "http://example.test/v1",
        "http://localhost:8080/v1",
        "https://example.test/v1",
    ],
)
def test_unapproved_base_urls_are_refused_by_default(monkeypatch, base_url):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_BASE_URL", base_url)

    result = run(server.mimo_ask(prompt="hello"))

    assert_refused_without_request(result)


@pytest.mark.parametrize(
    ("base_url", "expected_url"),
    [
        ("http://localhost:8080/v1", "http://localhost:8080/v1/chat/completions"),
        ("http://127.0.0.1:8080/v1", "http://127.0.0.1:8080/v1/chat/completions"),
        ("http://[::1]:8080/v1", "http://[::1]:8080/v1/chat/completions"),
    ],
)
def test_local_http_requires_insecure_local_opt_in(monkeypatch, base_url, expected_url):
    set_key(monkeypatch)
    if base_url.startswith("http://[::1]"):
        assert urlparse(base_url).hostname == "::1"
    monkeypatch.setenv("MIMO_BASE_URL", base_url)
    monkeypatch.setenv("MIMO_ALLOW_INSECURE_LOCAL_HTTP", "1")

    result = run(server.mimo_ask(prompt="hello"))

    assert "MiMo answer" in result
    assert FakeAsyncClient.requests[0]["url"] == expected_url


def test_public_http_is_refused_even_with_opt_ins(monkeypatch):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_BASE_URL", "http://example.test/v1")
    monkeypatch.setenv("MIMO_ALLOW_CUSTOM_BASE_URL", "1")
    monkeypatch.setenv("MIMO_ALLOW_INSECURE_LOCAL_HTTP", "1")

    result = run(server.mimo_ask(prompt="hello"))

    assert_refused_without_request(result)


def test_custom_https_requires_custom_base_url_opt_in(monkeypatch):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("MIMO_ALLOW_CUSTOM_BASE_URL", "1")

    result = run(server.mimo_ask(prompt="hello"))

    assert "MiMo answer" in result
    assert FakeAsyncClient.requests[0]["url"] == "https://example.test/v1/chat/completions"


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user@token-plan-cn.xiaomimimo.com/v1",
        "https://user:pass@token-plan-cn.xiaomimimo.com/v1",
        "https://token-plan-cn.xiaomimimo.com/v1?x=1",
        "https://token-plan-cn.xiaomimimo.com/v1#fragment",
        "https://user@example.test/v1",
        "https://example.test/v1?x=1",
        "https://example.test/v1#fragment",
    ],
)
def test_userinfo_query_and_fragment_are_refused_in_all_modes(monkeypatch, base_url):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_BASE_URL", base_url)
    monkeypatch.setenv("MIMO_ALLOW_CUSTOM_BASE_URL", "1")

    result = run(server.mimo_ask(prompt="hello"))

    assert_refused_without_request(result)


def test_invalid_base_url_returns_error_before_request(monkeypatch):
    set_key(monkeypatch)
    monkeypatch.setenv("MIMO_BASE_URL", "not-a-url")

    result = run(server.mimo_ask(prompt="hello"))

    assert result == "Error: MIMO_BASE_URL must be a valid http or https URL."
    assert FakeAsyncClient.requests == []


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, "authentication failed"),
        (403, "authentication failed"),
        (429, "rate limit"),
    ],
)
def test_common_http_errors_are_clear(monkeypatch, status_code, expected):
    set_key(monkeypatch)
    FakeAsyncClient.response = FakeResponse({}, status_code=status_code, text="do not expose key")

    result = run(server.mimo_review(context="review this"))

    assert expected in result


def test_empty_api_answer_returns_error(monkeypatch):
    set_key(monkeypatch)
    FakeAsyncClient.response = FakeResponse(
        {
            "choices": [{"finish_reason": "stop", "message": {"content": "   ", "role": "assistant"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
        }
    )

    result = run(server.mimo_compare(options="A vs B"))

    assert result.startswith("Error: MiMo API returned empty content.")
    assert "- finish_reason: stop" in result
    assert "- message_keys: ['content', 'role']" in result
    assert "- budget_mode: auto" in result
    assert "- completion_budget: 131072" in result
    assert "prompt_tokens" in result


def test_all_mcp_tools_are_importable():
    for name in ("mimo_ask", "mimo_summarize", "mimo_review", "mimo_test_draft", "mimo_compare"):
        assert hasattr(server, name)
        assert callable(getattr(server, name))
