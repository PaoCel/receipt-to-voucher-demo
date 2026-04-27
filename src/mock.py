"""Mock provider — runs the pipeline end-to-end without an API key.

Used when the CLI is invoked with `--llm-provider mock`. Maps the filename of
the input image to a pre-canned Receipt extraction. The deterministic validator
then runs as normal on the mocked output. The categorizer also has a mock that
returns a sensible adjustment.

The three fixtures shipped in `fixtures/` are scoped to demonstrate three
distinct outcomes:

  - `cafe_roma`     → clean meal receipt, high confidence → auto-approved
  - `grand_hotel`   → lodging, AI extracted a tax inconsistency the deterministic
                      validator catches → flagged for human review
  - `quick_buy`     → convenience-store mixed purchase, AI low confidence →
                      flagged for human review

This file ships zero real personal data. All numbers and merchants are invented.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from src.schema import Receipt, ReceiptLineItem


def _today() -> date:
    return date.today()


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


def _last_week() -> date:
    return date.today() - timedelta(days=6)


_MOCK_RECEIPTS: dict[str, Receipt] = {
    "cafe_roma": Receipt(
        merchant="Cafe Roma",
        vat_number="IT12345678901",
        issue_date=_yesterday(),
        currency="EUR",
        items=[
            ReceiptLineItem(description="Espresso", quantity=2, unit_price=1.20, total=2.40),
            ReceiptLineItem(description="Cornetto", quantity=2, unit_price=1.50, total=3.00),
        ],
        subtotal=5.40,
        tax=0.54,
        total=5.94,
        category="meals",
        confidence=0.93,
    ),
    "grand_hotel": Receipt(
        merchant="Grand Hotel Centrale",
        vat_number="IT99887766554",
        issue_date=_last_week(),
        currency="EUR",
        items=[
            ReceiptLineItem(description="Room (1 night)", quantity=1, unit_price=145.00, total=145.00),
            ReceiptLineItem(description="City tax", quantity=1, unit_price=4.00, total=4.00),
        ],
        # Deliberately inconsistent: the AI saw subtotal 149 + tax 14.5 but the
        # printed total is 155.50 — validator should catch this.
        subtotal=149.00,
        tax=14.50,
        total=155.50,
        category="lodging",
        confidence=0.81,
    ),
    "quick_buy": Receipt(
        merchant="Quick Buy 24",
        vat_number=None,
        issue_date=_today(),
        currency="EUR",
        items=[
            ReceiptLineItem(description="Acqua naturale 1L", quantity=2, unit_price=0.80, total=1.60),
            ReceiptLineItem(description="Sandwich", quantity=1, unit_price=4.50, total=4.50),
            ReceiptLineItem(description="Power bank (?)", quantity=1, unit_price=14.90, total=14.90),
        ],
        subtotal=21.00,
        tax=2.10,
        total=23.10,
        category="other",
        # Low confidence: mixed purchase, the AI is unsure of the category.
        confidence=0.58,
    ),
}


def mock_extract(image_path: Path | str) -> Receipt:
    """Return a pre-canned Receipt based on the filename stem.

    Falls back to a deliberately low-confidence "unknown" Receipt if the stem is
    not in the fixtures table — the deterministic validator will then flag it.
    """
    stem = Path(image_path).stem.lower()

    # Allow stems like "01_cafe_roma" or "cafe-roma" to match.
    for key, receipt in _MOCK_RECEIPTS.items():
        if key in stem:
            return receipt.model_copy(deep=True)

    return Receipt(
        merchant="UNKNOWN MOCK",
        total=0.0,
        confidence=0.10,
        needs_human_review=True,
        review_reason=f"mock provider has no fixture for stem '{stem}'",
    )


def mock_categorize(receipt: Receipt) -> Receipt:
    """Mirror what the real categorizer would do, deterministically.

    For mock fixtures we leave the category as the extractor returned it and
    apply a small confidence bump if the merchant matches a known category-stable
    pattern (e.g. obvious meal merchants). This keeps the demo coherent.
    """
    name = (receipt.merchant or "").lower()

    if any(token in name for token in ("cafe", "ristorante", "pizzeria", "trattoria")):
        receipt.category = "meals"
        receipt.confidence = round(min(1.0, receipt.confidence + 0.03), 3)
    elif "hotel" in name or "lodging" in name:
        receipt.category = "lodging"
    elif "quick" in name or "store" in name or "buy" in name:
        # Convenience-store mixed purchases: explicitly leave as "other" and lower
        # confidence — to demonstrate the human-review routing.
        receipt.category = "other"
        receipt.confidence = round(max(0.0, receipt.confidence - 0.05), 3)

    return receipt
