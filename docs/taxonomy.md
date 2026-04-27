# Expense taxonomy

This is the live taxonomy used by `src/categorize.py`. It is loaded at runtime; edit and re-run.

The taxonomy is intentionally short — six top-level categories cover the bulk of T&E expenses. Sub-categorisation is out of scope for this demo and would happen downstream in the ERP.

| Category | Definition | Typical examples | NOT this |
|---|---|---|---|
| `travel` | Movement between locations for a business purpose. | Train ticket; flight; taxi; ride-share; rental car; tolls; parking when traveling. | A receipt from a hotel — that's `lodging`. |
| `meals` | Food and beverage consumed during a business trip or business meeting. | Restaurant; café; bar (if business meal); minibar charge. | A grocery shop — that goes under `supplies` if for an office or `other` otherwise. |
| `lodging` | Overnight accommodation. | Hotel folio; B&B; serviced apartment. | Resort spa charges on the same folio — split, route the spa portion to `other` and flag for review. |
| `office` | Office services and equipment used at the workplace. | Printer toner; small electronics; office stationery purchased at a B2B supplier; co-working day pass. | A laptop above the company capitalisation threshold (capex, not opex) — flag for review. |
| `supplies` | Consumables purchased for a specific event or workstream. | Conference snacks; whiteboard markers for an offsite; tickets to a client event. | Personal items inadvertently included on the same receipt — flag for review. |
| `other` | Anything that does not fit the above. **Default for ambiguous receipts.** | Mixed-purchase convenience-store run; gifts; charitable donations from petty cash. | Anything you are confident belongs to a named category — pick the named one. |

## Configurability

This file is the taxonomy of record. To extend:

1. Add the new category here, with definition and examples.
2. Update the `ExpenseCategory` Literal in `src/schema.py`.
3. Re-run the test suite: `pytest`.

The LLM classifier reads this file verbatim into the prompt, so prose changes here flow into classification quality on the next run. Keep examples specific.

## Anti-patterns

- **Don't** use this taxonomy as a tax classification. Tax categories live in the ERP and depend on jurisdiction, supplier VAT regime, and recoverability rules. This taxonomy is a **bookkeeping shorthand**, not a tax basis.
- **Don't** expand to 20+ categories — the model's classification accuracy drops and reviewers struggle to remember boundaries. If you need more granularity, do it as sub-categories (a second field) rather than as more top-level categories.
