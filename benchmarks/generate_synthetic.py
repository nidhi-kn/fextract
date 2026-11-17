"""Generate privacy-safe synthetic invoices and matching labelled JSON."""

from pathlib import Path
import json
import random
import io


def generate(output: Path, count: int = 24, seed: int = 31) -> int:
    """Write privacy-safe invoice and statement PDFs with matching truth."""
    rng = random.Random(seed)
    sample_dir, truth_dir = output / "samples", output / "ground_truth"
    sample_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        is_invoice = index % 2 == 0
        number = f"SYN-{index + 1:04d}"
        target = sample_dir / f"{number}.pdf"
        bank_values = None
        if is_invoice:
            total = rng.randint(100, 9999) + rng.randint(0, 99) / 100
            name = f"Example Supplier {index + 1}"
            number_label = "Invoice No" if index % 4 else "Invoice Number"
            date_label = "Invoice Date" if index % 3 else "Date"
            text = f"COMMERCIAL INVOICE\n{number_label}: {number}\n{date_label}: 01/02/2025\nVendor: {name}\nGrand Total: INR {total:.2f}\n"
            fields = {
                "invoice_number": number,
                "invoice_date": "2025-02-01",
                "vendor_name": name,
                "total_sales_value": total,
                "currency": "INR",
            }
        else:
            debit = rng.randint(10, 500)
            opening = rng.randint(1000, 9000)
            closing = opening - debit
            text = (
                "BANK STATEMENT\nStatement Period: 01/02/2025 - 01/02/2025\n"
                f"Txn Date Description Debit Credit Balance\n"
                f"01/02/2025 Synthetic purchase {debit:.2f} 0.00 {closing:.2f}\n"
            )
            bank_values = (debit, closing)
            fields = {
                "period_start": "2025-02-01",
                "period_end": "2025-02-01",
                "opening_balance": float(opening),
                "closing_balance": float(closing),
            }
        import fitz

        pdf = fitz.open()
        page = pdf.new_page()
        if bank_values is None:
            page.insert_text((45 + index % 3 * 15, 70), text, fontsize=10 + index % 3)
        else:
            debit, closing = bank_values
            page.insert_text((45, 50), "BANK STATEMENT", fontsize=10)
            page.insert_text(
                (45, 70), "Statement Period: 01/02/2025 - 01/02/2025", fontsize=10
            )
            for x, label in (
                (45, "Txn Date"),
                (150, "Description"),
                (340, "Debit"),
                (420, "Credit"),
                (500, "Balance"),
            ):
                page.insert_text((x, 100), label, fontsize=10)
            for x, value in (
                (45, "01/02/2025"),
                (150, "Synthetic purchase"),
                (340, f"{debit:.2f}"),
                (420, "0.00"),
                (500, f"{closing:.2f}"),
            ):
                page.insert_text((x, 120), value, fontsize=10)
        pdf.save(target)
        pdf.close()
        truth = {"source_file": target.name, "fields": fields}
        (truth_dir / f"{number}.json").write_text(
            json.dumps(truth, indent=2), encoding="utf-8"
        )
        source_pdf = fitz.open(target)
        pixmap = source_pdf[0].get_pixmap(
            matrix=fitz.Matrix(90 / 72, 90 / 72), alpha=False
        )
        source_pdf.close()
        from PIL import Image, ImageFilter

        degraded_image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        degraded_image = degraded_image.rotate(
            rng.choice([-1.0, 1.0]),
            resample=Image.Resampling.BICUBIC,
            fillcolor="white",
        ).filter(ImageFilter.GaussianBlur(radius=0.35))
        image_bytes = io.BytesIO()
        degraded_image.save(image_bytes, format="JPEG", quality=48, optimize=True)
        degraded_pdf = fitz.open()
        degraded_page = degraded_pdf.new_page(width=612, height=792)
        degraded_page.insert_image(degraded_page.rect, stream=image_bytes.getvalue())
        degraded_path = sample_dir / f"{number}-degraded.pdf"
        degraded_pdf.save(degraded_path)
        degraded_pdf.close()
        degraded_truth = {"source_file": degraded_path.name, "fields": fields}
        (truth_dir / f"{number}-degraded.json").write_text(
            json.dumps(degraded_truth, indent=2), encoding="utf-8"
        )
        transcription = {"pages": {"1": text}}
        (truth_dir / f"{number}.ocr.json").write_text(
            json.dumps(transcription, indent=2), encoding="utf-8"
        )
        (truth_dir / f"{number}-degraded.ocr.json").write_text(
            json.dumps(transcription, indent=2), encoding="utf-8"
        )
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--count", type=int, default=24)
    args = parser.parse_args()
    print(f"Generated {generate(args.output, args.count)} synthetic records")
