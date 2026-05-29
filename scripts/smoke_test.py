#!/usr/bin/env python3
"""Smoke test for the MiMo MCP toolbox.

Run with:
    python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import mimo_ask  # noqa: E402


async def main() -> int:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if not os.environ.get("MIMO_TP_KEY"):
        print("SKIP: MIMO_TP_KEY is not set; smoke test did not call MiMo.")
        return 0

    result = await mimo_ask(prompt="Reply with a short confirmation that MiMo MCP smoke test works.", max_tokens=128)
    if result.startswith("Error:"):
        print(result)
        return 1

    answer, _, usage = result.partition("---\nusage report:")
    short_answer = answer.strip().replace("\n", " ")[:300]
    print(f"SUCCESS: {short_answer}")
    if usage:
        print("---")
        print("usage report:" + usage)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
