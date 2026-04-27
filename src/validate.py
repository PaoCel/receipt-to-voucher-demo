"""Deterministic validation layered over LLM extraction.

Pure Python, no LLM calls. Sets `needs_human_review` and `review_reason` on the
Receipt. The list of checks is deliberately conservative: we flag for human
review on any meaningful inconsistency rather than silently correcting.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from src.schema import Receipt

DEFAULT_REVIEW_THRESHOLD = float(os.environ.get("REVIEW_CONFIDENCE_THRESHOLD", "0.75"))
LINE_ITEM_TOLERANCE = 0.02
TOTAL_TOLERANCE = 0.02
MAX_AGE_DAYS = 730


def validate(receipt: Receipt, threshold: float | None = None) -> Receipt:
    """Run all checks; mutate `needs_human_review` / `review_reason` on the Receipt."""
    threshold = threshold if threshold is not None else DEFAULT_REVIEW_THRESHOLD
    reasons: list[str] = []

    # 1. Confidence threshold
    if receipt.confidence < threshold:
        reasons.append(f"confidence {receipt.confidence:.2f} below threshold {threshold:.2f}")

    # 2. Line items sum vs subtotal
    if receipt.items and receipt.subtotal is not None:
        line_sum = sum(item.total for item in receipt.items)
        if abs(line_sum - receipt.subtotal) > LINE_ITEM_TOLERANCE:
            reasons.append(
                f"line items sum ({line_sum:.2f}) ≠ subtotal ({receipt.subtotal:.2f})"
            )

    # 3. Subtotal + tax vs total
    if receipt.subtotal is not None and receipt.tax is not None:
        computed_total = receipt.subtotal + receipt.tax
        if abs(computed_total - receipt.total) > TOTAL_TOLERANCE:
            reasons.append(
                f"subtotal+tax ({computed_total:.2f}) ≠ total ({receipt.total:.2f})"
            )

    # 4. Issue date in plausible range
    if receipt.issue_date is not None:
        today = date.today()
        if receipt.issue_date > today:
            reasons.append(f"issue_date {receipt.issue_date.isoformat()} is in the future")
        elif receipt.issue_date < today - timedelta(days=MAX_AGE_DAYS):
            reasons.append(
                f"issue_date {receipt.issue_date.isoformat()} is older than "
                f"{MAX_AGE_DAYS} days"
            )

    # 5. Total must be positive
    if receipt.total <= 0:
        reasons.append(f"total ({receipt.total:.2f}) is not positive")

    # 6. Merchant name sanity
    if not receipt.merchant or len(receipt.merchant.strip()) < 2:
        reasons.append("merchant name missing or implausibly short")

    receipt.needs_human_review = bool(reasons)
    receipt.review_reason = "; ".join(reasons) if reasons else None
    return receipt
