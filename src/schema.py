"""Pydantic data model for receipts and processed voucher-ready output."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ExpenseCategory = Literal["travel", "meals", "lodging", "office", "supplies", "other"]
Currency = Literal["EUR", "USD", "GBP", "CHF"]


class ReceiptLineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    total: float


class Receipt(BaseModel):
    merchant: str
    vat_number: str | None = None
    issue_date: date | None = None
    currency: Currency = "EUR"
    items: list[ReceiptLineItem] = Field(default_factory=list)
    subtotal: float | None = None
    tax: float | None = None
    total: float
    category: ExpenseCategory = "other"
    confidence: float = Field(ge=0, le=1)
    needs_human_review: bool = False
    review_reason: str | None = None
