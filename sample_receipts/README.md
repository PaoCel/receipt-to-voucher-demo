# Sample receipts

Drop 3–5 receipt images here (`.jpg`, `.jpeg`, `.png`, `.webp`) to try the pipeline.

## Privacy hints

This is a public repo. Before adding a real receipt:

1. **Blur or crop** any name, address, P. IVA / VAT number, card number, loyalty number, or QR code that could re-identify you, the merchant, or another customer.
2. Prefer **synthetic** receipts (a receipt you generate or photograph from a publicly available example) over personal ones.
3. If you must use a personal receipt, drop it under `sample_receipts/private/` instead — that path is `.gitignore`d and will never be committed.

The pipeline does not care which sub-folder a receipt lives in; pass the directory you want processed via the CLI.

## Suggested seed set

- One restaurant receipt (meals).
- One taxi or train ticket (travel).
- One hotel folio (lodging).
- One office supply receipt (office / supplies).
- One ambiguous receipt (e.g. a mixed-purchase convenience-store run) — to demonstrate the human-review routing.
