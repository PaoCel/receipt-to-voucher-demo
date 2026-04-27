"""Refine the expense category of an extracted receipt via a second LLM pass.

The taxonomy (categories + descriptions) is loaded from `docs/taxonomy.md` so
that operators can edit categories without touching code.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Literal, get_args

from src.schema import ExpenseCategory, Receipt

LLMProvider = Literal["openai", "anthropic", "mock"]

DEFAULT_OPENAI_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini")
DEFAULT_ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_TEXT_MODEL", "claude-haiku-4-5-20251001")

TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "docs" / "taxonomy.md"

SYSTEM_PROMPT = (
    "You classify business expense receipts into a fixed taxonomy. "
    "Return JSON only. If the receipt is ambiguous, return category='other' "
    "and lower the confidence."
)


def _load_taxonomy() -> str:
    if TAXONOMY_PATH.exists():
        return TAXONOMY_PATH.read_text(encoding="utf-8")
    return "travel, meals, lodging, office, supplies, other"


def _build_user_prompt(receipt: Receipt) -> str:
    valid = ", ".join(get_args(ExpenseCategory))
    payload = {
        "merchant": receipt.merchant,
        "items": [item.description for item in receipt.items[:20]],
        "total": receipt.total,
        "currency": receipt.currency,
    }
    return (
        f"Taxonomy reference (do not output this back, just use it):\n\n"
        f"{_load_taxonomy()}\n\n"
        f"Receipt to classify:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        f"Return JSON: {{\"category\": one of [{valid}], "
        f"\"confidence_adjustment\": number between -0.3 and +0.1}}"
    )


def _strip_code_fence(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    return text


def _classify_openai(prompt: str) -> dict:
    from openai import OpenAI

    client = OpenAI()
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=DEFAULT_OPENAI_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except Exception as exc:
            last_err = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"OpenAI categorization failed: {last_err}") from last_err


def _classify_anthropic(prompt: str) -> dict:
    from anthropic import Anthropic

    client = Anthropic()
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=DEFAULT_ANTHROPIC_MODEL,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text if resp.content else "{}"
            text = _strip_code_fence(text)
            start = text.find("{")
            end = text.rfind("}")
            return json.loads(text[start : end + 1] if start != -1 else "{}")
        except Exception as exc:
            last_err = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Anthropic categorization failed: {last_err}") from last_err


def categorize(receipt: Receipt, provider: LLMProvider = "openai") -> Receipt:
    """Re-assign category and adjust confidence on a Receipt."""
    if provider == "mock":
        from src.mock import mock_categorize

        return mock_categorize(receipt)

    prompt = _build_user_prompt(receipt)
    raw = _classify_openai(prompt) if provider == "openai" else _classify_anthropic(prompt)

    proposed = raw.get("category")
    if proposed in get_args(ExpenseCategory):
        receipt.category = proposed

    try:
        adj = float(raw.get("confidence_adjustment", 0.0))
    except (TypeError, ValueError):
        adj = 0.0
    adj = max(-0.3, min(0.1, adj))
    receipt.confidence = round(max(0.0, min(1.0, receipt.confidence + adj)), 3)

    return receipt
