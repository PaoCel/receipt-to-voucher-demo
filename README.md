# receipt-to-voucher-demo

Extract structured data from receipt images, classify the expense, validate the result, and route low-confidence items to human review. Produces voucher-ready JSON plus a markdown batch report.

This is the canonical analog of journal-voucher data entry: scattered, photographic source data → structured ledger-grade rows, with the human kept in the loop wherever the model is uncertain.

## The point of this demo: AI agent + automation, layered

Two paradigms with different costs and different failure modes are stacked on purpose:

| Layer | Paradigm | What it does | What it costs | Where it fails |
|---|---|---|---|---|
| `extract.py`, `categorize.py` | **AI agent** | Reads a free-form receipt image, fills a strict schema, picks a category from a documented taxonomy | $$ per call, depends on model + image size | Improvises when unsure → can return wrong but plausible numbers |
| `validate.py` | **Deterministic automation** | Pure-Python checks: line-item sum vs subtotal, subtotal + tax vs total, date plausibility, merchant sanity, confidence threshold | $0, instant | Only catches what the developer encoded — invisible to anything outside the rules |
| (orchestrator) | Routes anything below threshold or any failed check to a human queue | — | A human costs more than a machine but exists for the case where neither the AI nor the rules can be trusted alone |

This is the position the demo defends: **automation gives guarantees you can audit, AI gives flexibility you cannot pre-script. Use both, layered. Never one without the other on data that matters.**

For a Finance team that owns journal vouchers, the same shape applies: AI extracts the noisy supplier text, automation enforces the deterministic invariants of the GL, the human signs off when either layer flags doubt.

## Why this repo exists

A small, public, opinionated demo of the shape of work an AI Developer does for a Finance & Records team. It is scoped as a **portfolio piece**: synthetic or personal receipts only, not connected to any real ledger, the data model deliberately decoupled from any specific ERP.

## Demo offline in 60 seconds (no API key needed)

The repo ships three fixtures and a `mock` provider so you can see the whole pipeline run without hitting any LLM API. One ricevuta auto-approves, one is caught by the math validator (AI extracted an inconsistent total), one is flagged for human review on confidence.

```bash
git clone https://github.com/paocel/receipt-to-voucher-demo.git
cd receipt-to-voucher-demo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline ./fixtures --llm-provider mock --out ./out
cat out/report.md
```

Expected output: a batch report with **1 auto-approved · 2 needing review** plus three JSON files in `out/`. Inspect `out/grand_hotel.json` to see the validator's diagnosis (`"review_reason": "subtotal+tax (163.50) ≠ total (155.50)"`) — the AI returned plausible-looking numbers, the deterministic layer caught the inconsistency.

## Tests

```bash
python -m pytest -q
```

Twelve unit tests on the deterministic validator. No API key needed.

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

## Real LLM run (with API key)

```bash
cp .env.example .env  # then edit and set OPENAI_API_KEY (or ANTHROPIC_API_KEY)
python -m src.pipeline ./sample_receipts --out ./out                     # OpenAI default
python -m src.pipeline ./sample_receipts --out ./out --llm-provider anthropic
```

Drop your own receipt images (`.jpg`, `.png`, `.webp`) into `sample_receipts/`. The folder ships with a README documenting privacy hygiene; real personal receipts go under `sample_receipts/private/` which is `.gitignore`d.

Recommended: set a hard usage cap on the OpenAI side at platform.openai.com → Settings → Limits. Per-receipt cost with `gpt-4o` is roughly $0.005-0.01.

## Output shape

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
├── fixtures/               # offline mock fixtures (1x1 PNG placeholders)
├── sample_receipts/        # drop your own; nothing real shipped
├── src/
│   ├── schema.py           # Pydantic models
│   ├── extract.py          # Vision LLM → Receipt
│   ├── categorize.py       # Text LLM + taxonomy → category, confidence delta
│   ├── validate.py         # deterministic checks → human-review flag
│   ├── mock.py             # offline provider for `--llm-provider mock`
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
