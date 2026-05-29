#!/usr/bin/env python3
"""MiMo Token Plan read-only MCP server for Codex."""

from __future__ import annotations

import os
from typing import Literal

import httpx
from mcp.server.fastmcp import FastMCP

API_URL = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
DEFAULT_MODEL = "mimo-v2.5-pro"
DEFAULT_MAX_TOKENS = 4096
VALID_TASK_TYPES = {
    "summary",
    "review",
    "test_draft",
    "explain",
    "brainstorm",
    "other",
}

mcp = FastMCP("mimo-mcp")


def _build_messages(prompt: str, context: str | None, task_type: str | None) -> list[dict[str, str]]:
    system_parts = [
        "You are MiMo Token Plan, connected to Codex as a read-only auxiliary model.",
        "Only use the text explicitly provided by the caller.",
        "Do not claim to read local files, write files, execute commands, or access the caller's project.",
    ]
    if task_type:
        system_parts.append(f"Task type: {task_type}.")

    user_parts = []
    if context:
        user_parts.append(f"Context:\n{context}")
    user_parts.append(f"Prompt:\n{prompt}")

    return [
        {"role": "system", "content": "\n".join(system_parts)},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


@mcp.tool()
async def mimo_ask(
    prompt: str,
    context: str | None = None,
    task_type: Literal["summary", "review", "test_draft", "explain", "brainstorm", "other"] | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Ask MiMo Token Plan using only caller-provided text."""
    if not isinstance(prompt, str) or not prompt.strip():
        return "Error: prompt is required and must be a non-empty string."

    if context is not None and not isinstance(context, str):
        return "Error: context must be a string when provided."

    if task_type is not None and task_type not in VALID_TASK_TYPES:
        allowed = ", ".join(sorted(VALID_TASK_TYPES))
        return f"Error: task_type must be one of: {allowed}."

    if not isinstance(model, str) or not model.strip():
        return "Error: model must be a non-empty string."

    if not isinstance(max_tokens, int) or max_tokens <= 0:
        return "Error: max_tokens must be a positive integer."

    api_key = os.environ.get("MIMO_TP_KEY")
    if not api_key:
        return (
            "Error: MIMO_TP_KEY is not set. Set it in your shell or with "
            "launchctl setenv MIMO_TP_KEY '<your-token-plan-key>' before starting Codex."
        )

    payload = {
        "model": model,
        "messages": _build_messages(prompt.strip(), context, task_type),
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(API_URL, headers=headers, json=payload)
    except httpx.TimeoutException:
        return "Error: MiMo API request timed out after 60 seconds."
    except httpx.RequestError as exc:
        return f"Error: MiMo API request failed: {exc.__class__.__name__}: {exc}"

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
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return f"Error: MiMo API response did not include choices[0].message.content: {data}"

    if content is None:
        return ""
    if not isinstance(content, str):
        return str(content)
    return content


if __name__ == "__main__":
    mcp.run()
