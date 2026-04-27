# Fixtures — offline demo data

These three files are 1x1 transparent PNG placeholders. They exist only so that
`src/pipeline.py:_iter_receipts` finds something to iterate over when the
pipeline runs in mock mode (`--llm-provider mock`).

The actual "extracted" data is hard-coded in `src/mock.py`, keyed on the
filename stem. Three scenarios are shipped:

| File | Scenario | Expected outcome |
|---|---|---|
| `cafe_roma.png` | Clean meal receipt, two espressos and two cornetti, math consistent, high confidence | **Auto-approved** |
| `grand_hotel.png` | Lodging receipt where the AI extracted `subtotal + tax ≠ total` | **Flagged for review** by the deterministic validator |
| `quick_buy.png` | Convenience-store mixed purchase (water + sandwich + ambiguous "power bank"), low confidence | **Flagged for review** by the confidence threshold |

Run:

```bash
python -m src.pipeline ./fixtures --llm-provider mock --out ./out
cat out/report.md
```

You should see two tables: 1 auto-approved, 2 needing human review.

The mock fixtures contain **zero real personal data**. All merchants, VAT
numbers, and totals are invented for demonstration purposes only.
