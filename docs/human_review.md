# Human review runbook

A pipeline run produces two artefacts in `out/`:

- One `<receipt>.json` per processed image — the full Receipt object.
- One `report.md` — a batch summary split into "Auto-approved" and "Needs human review".

This runbook is for the human reviewer who handles the second table.

## What to verify

For each receipt in **Needs human review**:

1. Open the original image and the `<receipt>.json` side by side.
2. Compare the field-by-field reading the AI produced against what the image shows. Pay particular attention to:
   - **Total** — every other check downstream depends on this number.
   - **Date** — common failure mode is the AI swapping `MM/DD/YYYY` for `DD/MM/YYYY`.
   - **VAT number** — eight or eleven digits in IT, easy to miss the leading IT prefix.
3. Read the `review_reason` field. It tells you which check tripped:
   - `confidence X below threshold Y` — the model itself wasn't sure.
   - `line items sum ≠ subtotal` — usually a missed line item or a misread quantity.
   - `subtotal+tax ≠ total` — usually a misread tax line.
   - `issue_date is in the future` / `older than 730 days` — almost always a date format swap.
   - `total is not positive` — extraction failed or the receipt is a refund.

## How to feed corrections back

For this demo:

1. Edit the `<receipt>.json` directly with the correct values.
2. Set `"needs_human_review": false` and clear `"review_reason"`.
3. Save. Downstream consumers (in production: the ERP voucher importer) treat the JSON as authoritative.

If the issue is systematic — e.g. the same merchant is always misclassified — record it in your reviewer log so the next iteration of the pipeline can:

- Add a heuristic to `src/validate.py` to flag that merchant earlier.
- Update the taxonomy in `docs/taxonomy.md` with a clearer example.
- Add a regression test to `tests/`.

## Re-running the pipeline

To re-run the same batch (e.g. after fixing the taxonomy):

```bash
rm out/*.json out/report.md
python -m src.pipeline ./sample_receipts --out ./out
```

To run only a single receipt during debugging:

```bash
python -c "from pathlib import Path; from src.pipeline import _process_one; \
  print(_process_one(Path('sample_receipts/IMG_0001.jpg'), 'openai').model_dump_json(indent=2))"
```

## What this would look like in production

In a Finance setting, this runbook becomes:

- A reviewer queue UI (one card per item in **Needs human review**, side-by-side image + structured form).
- A signed correction trail in the audit log: who edited what, when, and what the AI had originally said.
- A weekly review of the deviation rate (% of items where the human disagreed) by category and by merchant — used to retire obsolete heuristics and to add new ones.
- Role-based access: reviewers see only their own queue; supervisors see aggregates; nobody but the auditor exports the full data.
- Integration with the ERP: an approved receipt fires a journal-voucher creation API call; the AI's confidence becomes a posting-attribute flag.
