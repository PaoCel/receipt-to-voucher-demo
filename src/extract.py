"""Extract structured Receipt fields from a receipt image via Vision LLM.

Default provider: OpenAI. Anthropic is supported via the same function signature.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from src.schema import Receipt

LLMProvider = Literal["openai", "anthropic"]

DEFAULT_OPENAI_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o")
DEFAULT_ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_VISION_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = (
    "You extract structured fields from receipt images for an expense-management pipeline. "
    "Be conservative: when a field is not clearly visible, return null. "
    "Confidence reflects your overall certainty as a number between 0 and 1. "
    "Categories: travel, meals, lodging, office, supplies, other. Pick 'other' if unsure."
)

USER_PROMPT = (
    "Extract the following fields and return JSON conforming to this schema:\n"
    "{\n"
    '  "merchant": string,\n'
    '  "vat_number": string | null,\n'
    '  "issue_date": "YYYY-MM-DD" | null,\n'
    '  "currency": "EUR" | "USD" | "GBP" | "CHF",\n'
    '  "items": [{"description": string, "quantity": number | null, '
    '"unit_price": number | null, "total": number}],\n'
    '  "subtotal": number | null,\n'
    '  "tax": number | null,\n'
    '  "total": number,\n'
    '  "category": "travel" | "meals" | "lodging" | "office" | "supplies" | "other",\n'
    '  "confidence": number\n'
    "}\n"
    "Return JSON only — no prose."
)


def _read_image_b64(image_path: Path) -> tuple[str, str]:
    media_type, _ = mimetypes.guess_type(str(image_path))
    if not media_type or not media_type.startswith("image/"):
        raise ValueError(f"Unsupported image type for {image_path}")
    data = image_path.read_bytes()
    return base64.standard_b64encode(data).decode("ascii"), media_type


def _extract_with_openai(image_path: Path) -> dict:
    from openai import OpenAI

    client = OpenAI()
    b64, media_type = _read_image_b64(image_path)

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_OPENAI_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": USER_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{b64}"},
                            },
                        ],
                    },
                ],
                temperature=0.0,
            )
            text = response.choices[0].message.content or "{}"
            return json.loads(text)
        except Exception as exc:
            last_err = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"OpenAI extraction failed after retries: {last_err}") from last_err


def _extract_with_anthropic(image_path: Path) -> dict:
    from anthropic import Anthropic

    client = Anthropic()
    b64, media_type = _read_image_b64(image_path)

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=DEFAULT_ANTHROPIC_MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": USER_PROMPT},
                        ],
                    }
                ],
            )
            text = response.content[0].text if response.content else "{}"
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("No JSON object in Anthropic response")
            return json.loads(text[start : end + 1])
        except Exception as exc:
            last_err = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Anthropic extraction failed after retries: {last_err}") from last_err


def extract_receipt(image_path: Path | str, provider: LLMProvider = "openai") -> Receipt:
    """Extract a Receipt from an image file.

    Falls back to a low-confidence placeholder Receipt that will be flagged for
    human review by the validator if extraction yields a parseable but invalid
    payload.
    """
    image_path = Path(image_path)

    if provider == "openai":
        raw = _extract_with_openai(image_path)
    elif provider == "anthropic":
        raw = _extract_with_anthropic(image_path)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    try:
        return Receipt.model_validate(raw)
    except ValidationError as exc:
        return Receipt(
            merchant=str(raw.get("merchant", "UNKNOWN")),
            total=float(raw.get("total", 0.0) or 0.0),
            confidence=0.0,
            needs_human_review=True,
            review_reason=f"Schema validation failed: {exc.errors()[:3]}",
        )
