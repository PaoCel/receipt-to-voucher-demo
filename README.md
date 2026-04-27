# receipt-to-voucher-demo

Extract structured data from receipt images, classify the expense, validate the result, and route low-confidence items to human review. Produces voucher-ready JSON plus a markdown batch report.

This is the canonical analog of journal-voucher data entry: scattered, photographic source data → structured ledger-grade rows, with the human kept in the loop wherever the model is uncertain.

## Why this exists

A small, public, opinionated demo of the shape of work an AI Developer does for a Finance & Records team:

- LLM extraction from images.
- LLM classification against a documented taxonomy.
- Deterministic validation as a separate, auditable layer.
- Human-in-the-loop routing as the default, not the exception.

The repo is scoped as a **portfolio piece**. It works on synthetic or personal receipts only. It is not connected to any real ledger or company data, and the data model is deliberately decoupled from any specific ERP.

## Pipeline

```
   image (.jpg / .png)
        │
        ▼
 ┌─────────────┐    Vision LLM
 │   extract   │  (OpenAI GPT-4o by default;
 └─────┬───────┘   Anthropic Claude available
       │           via --llm-provider)
       │
       ▼
 ┌─────────────┐    Text LLM + taxonomy from
 │  categorize │   docs/taxonomy.md
 └─────┬───────┘
       │
       ▼
 ┌─────────────┐    Pure Python:
 │  validate   │   confidence threshold,
 └─────┬───────┘   line-item math, date sanity,
       │           merchant sanity
       ▼
 ┌─────────────┐    out/<receipt>.json
 │   write     │   out/report.md
 └─────────────┘   (auto-approved + needs review)
```

## Quickstart

```bash
git clone https://github.com/<your-handle>/receipt-to-voucher-demo.git
cd receipt-to-voucher-demo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit and set OPENAI_API_KEY
python -m src.pipeline ./sample_receipts --out ./out
```

Switch provider:

```bash
python -m src.pipeline ./sample_receipts --out ./out --llm-provider anthropic
```

Run on a single receipt during debugging:

```bash
python -c "from pathlib import Path; from src.pipeline import _process_one; \
  print(_process_one(Path('sample_receipts/IMG_0001.jpg'), 'openai').model_dump_json(indent=2))"
```

## Output

- **`out/<image-stem>.json`** — full Receipt object with merchant, line items, totals, category, confidence, and the `needs_human_review` flag plus a human-readable `review_reason`.
- **`out/report.md`** — batch summary with two tables (auto-approved, needs review) and stats line at the top.

## Responsible AI choices made

This repo is small, but the disciplines below are explicit and intentional:

- **Human-in-the-loop by default.** Anything below the confidence threshold (configurable, default 0.75) is flagged. The pipeline never silently corrects.
- **Deterministic validation layered over LLM extraction.** `src/validate.py` contains zero LLM calls — line-item math, date plausibility, total-positivity, merchant sanity — so the second opinion is mechanical, not stochastic.
- **Conservative extraction prompt.** The system prompt instructs the model to return `null` for unsure fields and to express confidence as a single 0–1 number, rather than confabulating values.
- **Documented taxonomy with anti-patterns.** `docs/taxonomy.md` is the LLM's authority on classification — operators can edit it without touching code.
- **No training data leakage.** The repo ships no real receipts; users supply their own (synthetic or opt-in personal). `sample_receipts/private/` is `.gitignore`d.
- **No keys in source.** Credentials are read from `.env` via `python-dotenv`; `.env.example` documents the required variables.
- **Documented limits.** OCR struggles with crumpled receipts, low-light photographs, and non-Latin scripts. The validator has no opinion on tax-code correctness — that lives downstream.

## What this would look like in production

A finance team running this for real would extend it along these axes (none of which are in this demo):

- **Data classification at the prompt boundary.** Voucher data is internal-confidential, supplier data is restricted, employee personal data is protected — separate channels, separate retention.
- **Audit trail.** Every extract / categorize / validate / human-correction step lands in an append-only audit log keyed by user, ledger period, and request correlation ID. Append-only Firestore-style schema sketched in [paolocelestini.eu](https://celestini.eu/) work samples.
- **Role-based access for the reviewer queue.** Reviewers see only their queue; supervisors see aggregates; auditors export the full trail.
- **Integration with the Oracle ERP API.** A "Post to GL" button on a reviewed receipt fires a journal-voucher creation API call; the AI confidence becomes a posting-attribute flag the auditor can filter on.
- **Segregation-of-duties enforcement.** The user who extracted the receipt cannot be the user who approves it; both must be different from the user who posts to the ledger.
- **Continuous evaluation.** A weekly held-out batch with known-good answers benchmarks accuracy by category and by merchant; drift triggers a review of the prompt and taxonomy.
- **Sunset clause.** Any AI feature whose human-correction rate degrades for two consecutive months is paused and re-evaluated.

These extensions are why "AI Developer" is a meaningful job title rather than a wrapper around a chat completion call: most of the work is the surrounding system, not the model call.

## Tests

```bash
pytest
```

The included `tests/test_validate.py` covers the deterministic validator: confidence threshold, line-item math, subtotal+tax mismatch, future / very old dates, negative totals, merchant sanity, threshold override, tolerance band. New checks should ship with a paired test.

## Project layout

```
receipt-to-voucher-demo/
├── README.md
├── LICENSE                 # MIT
├── .gitignore
├── .env.example
├── requirements.txt
├── pyproject.toml
├── sample_receipts/        # drop your own; nothing real shipped
├── src/
│   ├── schema.py           # Pydantic models
│   ├── extract.py          # Vision LLM → Receipt
│   ├── categorize.py       # Text LLM + taxonomy → category, confidence delta
│   ├── validate.py         # deterministic checks → human-review flag
│   └── pipeline.py         # CLI orchestrator
├── docs/
│   ├── taxonomy.md
│   └── human_review.md
├── tests/
│   └── test_validate.py
└── out/                    # JSON + report.md (regenerated each run)
```

## Author

[Paolo Celestini](https://celestini.eu) — paolo@celestini.eu

Live products and working samples are linked from the personal site. This repo accompanies an application for an AI Developer role on a Finance & Records team and is sized to demonstrate the practitioner posture rather than to ship a product.
