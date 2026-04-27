"""CLI orchestrator: extract → categorize → validate → write JSON + report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.categorize import categorize
from src.extract import extract_receipt
from src.schema import Receipt
from src.validate import validate

LLMProvider = Literal["openai", "anthropic", "mock"]
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

console = Console()


def _iter_receipts(input_dir: Path) -> list[Path]:
    return sorted(p for p in input_dir.rglob("*") if p.suffix.lower() in SUPPORTED_EXTS)


def _process_one(image: Path, provider: LLMProvider) -> Receipt:
    receipt = extract_receipt(image, provider=provider)
    if not receipt.needs_human_review:
        receipt = categorize(receipt, provider=provider)
    return validate(receipt)


def _write_json(receipt: Receipt, image: Path, out_dir: Path) -> Path:
    out_path = out_dir / f"{image.stem}.json"
    out_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def _write_report(records: list[tuple[Path, Receipt]], out_dir: Path) -> Path:
    report_path = out_dir / "report.md"
    auto_approved = [(p, r) for p, r in records if not r.needs_human_review]
    needs_review = [(p, r) for p, r in records if r.needs_human_review]

    lines = [
        "# Batch report",
        "",
        f"- Total receipts processed: **{len(records)}**",
        f"- Auto-approved: **{len(auto_approved)}**",
        f"- Needs human review: **{len(needs_review)}**",
        "",
        "## Auto-approved",
        "",
        "| File | Merchant | Date | Category | Total | Confidence |",
        "|------|----------|------|----------|------:|----------:|",
    ]
    for image, receipt in auto_approved:
        lines.append(
            f"| `{image.name}` | {receipt.merchant} | "
            f"{receipt.issue_date or '—'} | {receipt.category} | "
            f"{receipt.total:.2f} {receipt.currency} | {receipt.confidence:.2f} |"
        )
    if not auto_approved:
        lines.append("| _none_ | | | | | |")

    lines.extend(
        [
            "",
            "## Needs human review",
            "",
            "| File | Merchant | Total | Confidence | Reason |",
            "|------|----------|------:|----------:|--------|",
        ]
    )
    for image, receipt in needs_review:
        lines.append(
            f"| `{image.name}` | {receipt.merchant} | "
            f"{receipt.total:.2f} {receipt.currency} | "
            f"{receipt.confidence:.2f} | {receipt.review_reason or '—'} |"
        )
    if not needs_review:
        lines.append("| _none_ | | | | |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Extract structured voucher data from receipts.")
    parser.add_argument("input_dir", type=Path, help="Directory containing receipt images.")
    parser.add_argument(
        "--out", type=Path, default=Path("out"), help="Output directory (default: ./out)."
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "anthropic", "mock"],
        default="openai",
        help="LLM provider for extract + categorize. 'mock' runs offline against shipped fixtures.",
    )
    args = parser.parse_args(argv)

    if not args.input_dir.exists():
        console.print(f"[red]Input directory not found: {args.input_dir}[/red]")
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    images = _iter_receipts(args.input_dir)
    if not images:
        console.print(f"[yellow]No receipt images found in {args.input_dir}[/yellow]")
        return 0

    records: list[tuple[Path, Receipt]] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing receipts…", total=len(images))
        for image in images:
            progress.update(task, description=f"Processing {image.name}")
            try:
                receipt = _process_one(image, provider=args.llm_provider)
            except Exception as exc:
                console.print(f"[red]Failed on {image.name}: {exc}[/red]")
                receipt = Receipt(
                    merchant="UNKNOWN",
                    total=0.0,
                    confidence=0.0,
                    needs_human_review=True,
                    review_reason=f"pipeline error: {exc}",
                )
            _write_json(receipt, image, args.out)
            records.append((image, receipt))
            progress.advance(task)

    report = _write_report(records, args.out)
    auto = sum(1 for _, r in records if not r.needs_human_review)
    review = len(records) - auto
    console.print(f"[green]Done.[/green] {auto} auto-approved · {review} need review · report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
