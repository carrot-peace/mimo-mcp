#!/usr/bin/env python3
"""MiMo Token Plan read-only MCP toolbox for Codex."""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, Literal
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP

DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
DEFAULT_MODEL = "mimo-v2.5-pro"
DEFAULT_COMPLETION_BUDGET = 65536
LARGE_COMPLETION_BUDGET = 131072
LONG_CONTEXT_CHARS = 20000
COMPLEX_QUESTION_CHARS = 500
REQUEST_TIMEOUT_SECONDS = 60.0
VALID_TASK_TYPES = {
    "summary",
    "review",
    "test_draft",
    "explain",
    "brainstorm",
    "other",
}
VALID_BUDGET_MODES = {"auto", "default", "large"}
APPROVED_MIMO_HOSTS = {
    "token-plan-cn.xiaomimimo.com",
    "token-plan-sgp.xiaomimimo.com",
    "token-plan-ams.xiaomimimo.com",
}
LOCAL_HTTP_HOSTS = {"localhost", "127.0.0.1", "::1"}
BASE_URL_REFUSED_ERROR = "Refused: MIMO_BASE_URL is not an approved MiMo endpoint."
BASE_URL_INVALID_ERROR = "Error: MIMO_BASE_URL must be a valid http or https URL."

mcp = FastMCP("mimo-mcp")


SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OpenAI-style API key", re.compile(r"(?i)(?:^|[^A-Za-z0-9_-])sk-[A-Za-z0-9_-]{12,}")),
    ("Token Plan API key", re.compile(r"(?i)(?:^|[^A-Za-z0-9_-])tp-[A-Za-z0-9_-]{8,}")),
    (
        "API key environment variable name",
        re.compile(
            r"(?i)\b(?:OPENAI|ANTHROPIC|GEMINI|GOOGLE|MIMO|MIMO_TP|TOKEN_PLAN)"
            r"[_-]*(?:API[_-]*)?(?:KEY|TOKEN|SECRET)\b"
        ),
    ),
    (
        "secret-like assignment",
        re.compile(
            r"(?im)^\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*(?:PASSWORD|PASSWD|PWD|TOKEN|SECRET|PRIVATE_KEY|ACCESS_KEY|API_KEY)"
            r"[A-Za-z0-9_]*\s*[:=]\s*['\"]?[^'\"\s#]{6,}"
        ),
    ),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    (
        ".env style secret",
        re.compile(
            r"(?im)^\s*[A-Za-z_][A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD)\s*=\s*['\"]?[^'\"\s#]{6,}"
        ),
    ),
    (
        "Android signing configuration",
        re.compile(r"(?im)^\s*(?:storePassword|keyPassword|keyAlias|storeFile)\s*[:=]\s*\S+"),
    ),
    (
        "Android key.properties content",
        re.compile(
            r"(?is)\bstorePassword\s*[:=].+\bkeyPassword\s*[:=].+\bkeyAlias\s*[:=].+\bstoreFile\s*[:=]"
        ),
    ),
)


def _env_default_model() -> str:
    return os.environ.get("MIMO_DEFAULT_MODEL") or DEFAULT_MODEL


def _env_base_url() -> str:
    return os.environ.get("MIMO_BASE_URL") or DEFAULT_BASE_URL


def _env_flag_enabled(name: str) -> bool:
    return os.environ.get(name) == "1"


def _normalized_base_path(path: str) -> str | None:
    if path in {"/v1", "/v1/"}:
        return "/v1"
    return None


def _chat_completions_url() -> tuple[str | None, str | None]:
    base_url = _env_base_url().strip()
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        return None, BASE_URL_INVALID_ERROR
    try:
        port = parsed.port
    except ValueError:
        return None, BASE_URL_INVALID_ERROR
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None, BASE_URL_REFUSED_ERROR

    normalized_path = _normalized_base_path(parsed.path)
    if normalized_path is None:
        return None, BASE_URL_REFUSED_ERROR

    host = parsed.hostname
    if parsed.scheme == "https":
        official_endpoint = host in APPROVED_MIMO_HOSTS and port is None
        if official_endpoint or _env_flag_enabled("MIMO_ALLOW_CUSTOM_BASE_URL"):
            netloc = parsed.netloc
            return f"https://{netloc}{normalized_path}/chat/completions", None
        return None, BASE_URL_REFUSED_ERROR

    if _env_flag_enabled("MIMO_ALLOW_INSECURE_LOCAL_HTTP") and host in LOCAL_HTTP_HOSTS:
        netloc = parsed.netloc
        return f"http://{netloc}{normalized_path}/chat/completions", None
    return None, BASE_URL_REFUSED_ERROR


def _input_limit() -> int:
    raw = os.environ.get("MIMO_MAX_INPUT_CHARS", "0").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _coerce_model(model: str | None) -> str:
    if model is None:
        return _env_default_model()
    return model


def _env_completion_budget(name: str, default: int) -> tuple[int, bool, str | None]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default, False, None
    try:
        value = int(raw.strip())
    except ValueError:
        return default, True, f"{name}=invalid"
    if value <= 0:
        return default, True, f"{name}=invalid"
    return value, False, None


def _normalize_budget_mode(budget: str) -> tuple[str, bool]:
    if not isinstance(budget, str):
        return "auto", True
    mode = budget.strip().lower()
    if mode not in VALID_BUDGET_MODES:
        return "auto", True
    return mode, False


def _auto_budget_mode(tool: str, user_sections: list[tuple[str, str]]) -> str:
    section_map = dict(user_sections)
    if tool == "mimo_compare":
        return "large"
    if tool == "mimo_summarize" and len(section_map.get("Context", "")) >= LONG_CONTEXT_CHARS:
        return "large"
    if tool == "mimo_review":
        context = section_map.get("Context", "")
        question = section_map.get("Question", "")
        if len(context) >= LONG_CONTEXT_CHARS or len(question) >= COMPLEX_QUESTION_CHARS:
            return "large"
    return "default"


def _resolve_completion_budget(
    *,
    tool: str,
    user_sections: list[tuple[str, str]],
    budget: str,
) -> tuple[str, int, bool, list[str]]:
    requested_mode, budget_fallback_used = _normalize_budget_mode(budget)
    effective_mode = _auto_budget_mode(tool, user_sections) if requested_mode == "auto" else requested_mode
    default_budget, default_fallback_used, default_note = _env_completion_budget(
        "MIMO_DEFAULT_COMPLETION_BUDGET", DEFAULT_COMPLETION_BUDGET
    )
    large_budget, large_fallback_used, large_note = _env_completion_budget(
        "MIMO_LARGE_COMPLETION_BUDGET", LARGE_COMPLETION_BUDGET
    )
    env_fallbacks = [
        note
        for used, note in ((default_fallback_used, default_note), (large_fallback_used, large_note))
        if used and note
    ]
    completion_budget = large_budget if effective_mode == "large" else default_budget
    return requested_mode, completion_budget, budget_fallback_used, env_fallbacks


def _find_sensitive_categories(texts: Iterable[str]) -> list[str]:
    categories: list[str] = []
    for text in texts:
        for category, pattern in SENSITIVE_PATTERNS:
            if pattern.search(text) and category not in categories:
                categories.append(category)
    return categories


def _usage_report(
    *,
    tool: str,
    model: str,
    budget_mode: str,
    completion_budget: int,
    budget_fallback_used: bool,
    env_budget_fallbacks: list[str],
    input_chars: int,
    output_chars: int,
    usage: dict[str, Any] | None,
) -> str:
    if model == "mimo-v2.5-pro":
        multiplier = "usually 2x (hint only, not exact billing)"
    elif model == "mimo-v2.5":
        multiplier = "usually 1x (hint only, not exact billing)"
    else:
        multiplier = "unknown"

    lines = [
        "",
        "---",
        "usage report:",
        f"- tool: {tool}",
        f"- model: {model}",
        f"- budget_mode: {budget_mode}",
        f"- completion_budget: {completion_budget}",
        f"- budget_fallback_used: {str(budget_fallback_used).lower()}",
        f"- env_budget_fallback_used: {str(bool(env_budget_fallbacks)).lower()}",
        f"- input_chars: {input_chars}",
        f"- output_chars: {output_chars}",
        f"- estimated_credit_multiplier: {multiplier}",
    ]
    if env_budget_fallbacks:
        lines.append(f"- env_budget_fallbacks: {', '.join(env_budget_fallbacks)}")
    if usage:
        lines.extend(
            [
                f"- prompt_tokens: {usage.get('prompt_tokens')}",
                f"- completion_tokens: {usage.get('completion_tokens')}",
                f"- total_tokens: {usage.get('total_tokens')}",
                "- usage_source: api_usage",
            ]
        )
    else:
        lines.append("- usage_source: not_reported")
    return "\n".join(lines)


def _empty_content_diagnostic(
    *,
    data: dict[str, Any],
    message: Any,
    finish_reason: Any,
    tool: str,
    model: str,
    budget_mode: str,
    completion_budget: int,
    budget_fallback_used: bool,
    env_budget_fallbacks: list[str],
) -> str:
    usage = data.get("usage")
    usage_value: Any = usage if isinstance(usage, dict) else None
    message_keys = sorted(message.keys()) if isinstance(message, dict) else []
    lines = [
        "Error: MiMo API returned empty content.",
        "diagnostic:",
        f"- tool: {tool}",
        f"- model: {model}",
        f"- finish_reason: {finish_reason}",
        f"- message_keys: {message_keys}",
        f"- usage: {usage_value if usage_value is not None else 'not_reported'}",
        f"- budget_mode: {budget_mode}",
        f"- completion_budget: {completion_budget}",
        f"- budget_fallback_used: {str(budget_fallback_used).lower()}",
        f"- env_budget_fallback_used: {str(bool(env_budget_fallbacks)).lower()}",
        "- possible_empty_content_source: server_or_model_returned_empty_content",
    ]
    if env_budget_fallbacks:
        lines.append(f"- env_budget_fallbacks: {', '.join(env_budget_fallbacks)}")
    return "\n".join(lines)


def _build_messages(system_prompt: str, user_sections: list[tuple[str, str]]) -> list[dict[str, str]]:
    system = "\n".join(
        [
            "You are MiMo Token Plan, connected to Codex as a read-only auxiliary model.",
            "Only use the text explicitly provided by the caller.",
            "Do not claim to read local files, write files, execute commands, scan projects, or apply patches.",
            system_prompt,
        ]
    )
    user = "\n\n".join(f"{title}:\n{body}" for title, body in user_sections if body)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


async def _call_mimo(
    *,
    tool: str,
    user_sections: list[tuple[str, str]],
    system_prompt: str,
    model: str | None,
    budget: str,
) -> str:
    if not user_sections or any(not isinstance(value, str) for _, value in user_sections):
        return "Error: all text parameters must be strings."

    required_values = [value for _, value in user_sections]
    if not any(value.strip() for value in required_values):
        return "Error: a non-empty text parameter is required."

    model_name = _coerce_model(model)
    if not isinstance(model_name, str) or not model_name.strip():
        return "Error: model must be a non-empty string when provided."
    model_name = model_name.strip()

    budget_mode, completion_budget, budget_fallback_used, env_budget_fallbacks = _resolve_completion_budget(
        tool=tool,
        user_sections=user_sections,
        budget=budget,
    )

    sensitive_categories = _find_sensitive_categories(required_values)
    if sensitive_categories:
        categories = ", ".join(sensitive_categories)
        return f"Error: refused to call MiMo API because input may contain sensitive content. Matched rule categories: {categories}."

    input_chars = sum(len(value) for value in required_values)
    limit = _input_limit()
    if limit > 0 and input_chars > limit:
        return (
            f"Error: input is {input_chars} characters, exceeding MIMO_MAX_INPUT_CHARS={limit}. "
            "Please reduce the provided context or increase MIMO_MAX_INPUT_CHARS."
        )

    api_key = os.environ.get("MIMO_TP_KEY")
    if not api_key:
        return (
            "Error: MIMO_TP_KEY is not set. Set it in your shell or with "
            "launchctl setenv MIMO_TP_KEY '<your-token-plan-key>' before starting Codex."
        )

    api_url, base_url_error = _chat_completions_url()
    if api_url is None:
        return base_url_error or BASE_URL_INVALID_ERROR

    payload = {
        "model": model_name,
        "messages": _build_messages(system_prompt, user_sections),
        "max_completion_tokens": completion_budget,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(api_url, headers=headers, json=payload)
    except httpx.TimeoutException:
        return f"Error: MiMo API request timed out after {int(REQUEST_TIMEOUT_SECONDS)} seconds."
    except httpx.RequestError as exc:
        return f"Error: MiMo API request failed: {exc.__class__.__name__}: {exc}"

    if response.status_code in {401, 403}:
        return f"Error: MiMo API authentication failed with HTTP {response.status_code}. Check MIMO_TP_KEY without sharing it."
    if response.status_code == 429:
        return "Error: MiMo API returned HTTP 429 rate limit. Please retry later."
    if response.status_code < 200 or response.status_code >= 300:
        detail = response.text.strip()
        if len(detail) > 1000:
            detail = detail[:1000] + "..."
        return f"Error: MiMo API returned HTTP {response.status_code}: {detail}"

    try:
        data = response.json()
    except ValueError:
        return "Error: MiMo API returned a non-JSON response."

    try:
        choice = data["choices"][0]
        message = choice["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError):
        return "Error: MiMo API response did not include choices[0].message.content."
    finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None

    if not isinstance(content, str):
        if content is None:
            return _empty_content_diagnostic(
                data=data,
                message=message,
                finish_reason=finish_reason,
                tool=tool,
                model=model_name,
                budget_mode=budget_mode,
                completion_budget=completion_budget,
                budget_fallback_used=budget_fallback_used,
                env_budget_fallbacks=env_budget_fallbacks,
            )
        content = str(content)
    if not content.strip():
        return _empty_content_diagnostic(
            data=data,
            message=message,
            finish_reason=finish_reason,
            tool=tool,
            model=model_name,
            budget_mode=budget_mode,
            completion_budget=completion_budget,
            budget_fallback_used=budget_fallback_used,
            env_budget_fallbacks=env_budget_fallbacks,
        )

    usage = data.get("usage")
    if not isinstance(usage, dict):
        usage = None
    return content + _usage_report(
        tool=tool,
        model=model_name,
        budget_mode=budget_mode,
        completion_budget=completion_budget,
        budget_fallback_used=budget_fallback_used,
        env_budget_fallbacks=env_budget_fallbacks,
        input_chars=input_chars,
        output_chars=len(content),
        usage=usage,
    )


@mcp.tool()
async def mimo_ask(
    prompt: str,
    context: str | None = None,
    task_type: Literal["summary", "review", "test_draft", "explain", "brainstorm", "other"] | None = None,
    model: str | None = None,
    budget: str = "auto",
) -> str:
    """Ask MiMo Token Plan using only caller-provided text."""
    if not isinstance(prompt, str) or not prompt.strip():
        return "Error: prompt is required and must be a non-empty string."
    if context is not None and not isinstance(context, str):
        return "Error: context must be a string when provided."
    if task_type is not None and task_type not in VALID_TASK_TYPES:
        allowed = ", ".join(sorted(VALID_TASK_TYPES))
        return f"Error: task_type must be one of: {allowed}."

    sections = []
    if context:
        sections.append(("Context", context))
    sections.append(("Prompt", prompt))
    task_line = f"Task type: {task_type}." if task_type else "General analysis task."
    return await _call_mimo(
        tool="mimo_ask",
        user_sections=sections,
        system_prompt=task_line,
        model=model,
        budget=budget,
    )


@mcp.tool()
async def mimo_summarize(
    context: str,
    focus: str | None = None,
    model: str | None = None,
    budget: str = "auto",
) -> str:
    """Summarize long caller-provided context."""
    if not isinstance(context, str) or not context.strip():
        return "Error: context is required and must be a non-empty string."
    if focus is not None and not isinstance(focus, str):
        return "Error: focus must be a string when provided."
    sections = [("Context", context)]
    if focus:
        sections.append(("Focus", focus))
    return await _call_mimo(
        tool="mimo_summarize",
        user_sections=sections,
        system_prompt=(
            "Summarize long code, diffs, or documents in a structured way. "
            "Separate facts, inferences, uncertainties, and important omissions."
        ),
        model=model,
        budget=budget,
    )


@mcp.tool()
async def mimo_review(
    context: str,
    question: str | None = None,
    model: str | None = None,
    budget: str = "auto",
) -> str:
    """Ask MiMo for a read-only second opinion on risks and gaps."""
    if not isinstance(context, str) or not context.strip():
        return "Error: context is required and must be a non-empty string."
    if question is not None and not isinstance(question, str):
        return "Error: question must be a string when provided."
    sections = [("Context", context)]
    if question:
        sections.append(("Question", question))
    return await _call_mimo(
        tool="mimo_review",
        user_sections=sections,
        system_prompt=(
            "Provide a second opinion focused only on risks, edge cases, potential bugs, and missing tests. "
            "Do not ask to modify code and do not give a final implementation decision; Codex decides."
        ),
        model=model,
        budget=budget,
    )


@mcp.tool()
async def mimo_test_draft(
    context: str,
    test_goal: str | None = None,
    model: str | None = None,
    budget: str = "auto",
) -> str:
    """Generate test ideas or draft tests from caller-provided context."""
    if not isinstance(context, str) or not context.strip():
        return "Error: context is required and must be a non-empty string."
    if test_goal is not None and not isinstance(test_goal, str):
        return "Error: test_goal must be a string when provided."
    sections = [("Context", context)]
    if test_goal:
        sections.append(("Test goal", test_goal))
    return await _call_mimo(
        tool="mimo_test_draft",
        user_sections=sections,
        system_prompt=(
            "Draft test scenarios, boundary cases, pseudocode, or test sketches. "
            "Do not assume project APIs that were not provided. Do not write files."
        ),
        model=model,
        budget=budget,
    )


@mcp.tool()
async def mimo_compare(
    options: str,
    criteria: str | None = None,
    model: str | None = None,
    budget: str = "auto",
) -> str:
    """Compare caller-provided options without unsupported claims."""
    if not isinstance(options, str) or not options.strip():
        return "Error: options is required and must be a non-empty string."
    if criteria is not None and not isinstance(criteria, str):
        return "Error: criteria must be a string when provided."
    sections = [("Options", options)]
    if criteria:
        sections.append(("Criteria", criteria))
    return await _call_mimo(
        tool="mimo_compare",
        user_sections=sections,
        system_prompt=(
            "Compare options by complexity, risk, maintainability, and test cost. "
            "Mark uncertainty clearly and avoid claims not supported by the provided evidence."
        ),
        model=model,
        budget=budget,
    )


if __name__ == "__main__":
    mcp.run()
