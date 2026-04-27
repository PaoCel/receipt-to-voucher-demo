"""Unit tests for the deterministic validator."""

from datetime import date, timedelta

import pytest

from src.schema import Receipt, ReceiptLineItem
from src.validate import validate


def _good_receipt(**overrides) -> Receipt:
    payload = dict(
        merchant="Cafe Roma",
        issue_date=date.today() - timedelta(days=2),
        currency="EUR",
        items=[ReceiptLineItem(description="espresso", quantity=2, unit_price=1.50, total=3.00)],
        subtotal=3.00,
        tax=0.66,
        total=3.66,
        category="meals",
        confidence=0.92,
    )
    payload.update(overrides)
    return Receipt(**payload)


def test_clean_receipt_does_not_need_review():
    receipt = validate(_good_receipt())
    assert receipt.needs_human_review is False
    assert receipt.review_reason is None


def test_low_confidence_triggers_review():
    receipt = validate(_good_receipt(confidence=0.40))
    assert receipt.needs_human_review is True
    assert "confidence" in (receipt.review_reason or "")


def test_line_items_mismatch_triggers_review():
    receipt = validate(
        _good_receipt(
            items=[ReceiptLineItem(description="espresso", total=3.00)],
            subtotal=10.00,
            tax=0.0,
            total=10.00,
        )
    )
    assert receipt.needs_human_review is True
    assert "line items" in (receipt.review_reason or "")


def test_subtotal_plus_tax_mismatch_triggers_review():
    receipt = validate(_good_receipt(subtotal=3.00, tax=0.66, total=99.99))
    assert receipt.needs_human_review is True
    assert "subtotal+tax" in (receipt.review_reason or "")


def test_future_date_triggers_review():
    receipt = validate(_good_receipt(issue_date=date.today() + timedelta(days=5)))
    assert receipt.needs_human_review is True
    assert "future" in (receipt.review_reason or "")


def test_old_date_triggers_review():
    receipt = validate(_good_receipt(issue_date=date.today() - timedelta(days=900)))
    assert receipt.needs_human_review is True
    assert "older than" in (receipt.review_reason or "")


def test_negative_total_triggers_review():
    receipt = validate(_good_receipt(total=-1.0, subtotal=None, tax=None, items=[]))
    assert receipt.needs_human_review is True
    assert "not positive" in (receipt.review_reason or "")


def test_short_merchant_triggers_review():
    receipt = validate(_good_receipt(merchant=""))
    assert receipt.needs_human_review is True
    assert "merchant" in (receipt.review_reason or "")


def test_threshold_override():
    receipt = validate(_good_receipt(confidence=0.80), threshold=0.95)
    assert receipt.needs_human_review is True


@pytest.mark.parametrize("delta", [-0.005, 0.0, 0.005])
def test_line_items_within_tolerance(delta):
    receipt = validate(
        _good_receipt(
            items=[ReceiptLineItem(description="espresso", total=3.00 + delta)],
            subtotal=3.00,
            tax=0.66,
            total=3.66 + delta,
        )
    )
    assert receipt.needs_human_review is False
