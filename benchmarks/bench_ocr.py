"""Compare embedded, Tesseract, and PaddleOCR text on local PDF pages."""

from pathlib import Path
import csv
import json
import time


def _distance(left: list[str], right: list[str]) -> int:
    """Compute edit distance using a memory-efficient dynamic-programming row."""
    previous = list(range(len(right) + 1))
    for row, left_token in enumerate(left, start=1):
        current = [row]
        for column, right_token in enumerate(right, start=1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left_token != right_token),
                )
            )
        previous = current
    return previous[-1]


def _error_rates(reference: str, candidate: str) -> tuple[float, float]:
    """Return word and character error rates for one transcription pair."""
    ref_words, out_words = reference.split(), candidate.split()
    wer = _distance(ref_words, out_words) / max(len(ref_words), 1)
    ref_chars, out_chars = list(reference), list(candidate)
    cer = _distance(ref_chars, out_chars) / max(len(ref_chars), 1)
    return wer, cer


def benchmark(
    samples: Path, ground_truth: Path, files: list[str] | None = None
) -> list[dict[str, object]]:
    """Measure each available engine; compare to optional per-document OCR truth."""
    import fitz
    from PIL import Image
    import io

    from fextract.ocr.paddle_engine import PaddleEngine
    from fextract.ocr.preprocess import preprocess
    from fextract.ocr.tesseract_engine import TesseractEngine

    rows = []
    pdf_paths = sorted(samples.glob("*.pdf"))
    if files:
        selected = set(files)
        pdf_paths = [path for path in pdf_paths if path.name in selected]
    for pdf_path in pdf_paths:
        truth_path = ground_truth / f"{pdf_path.stem}.ocr.json"
        truth_pages = (
            json.loads(truth_path.read_text(encoding="utf-8")).get("pages", {})
            if truth_path.exists()
            else {}
        )
        doc = fitz.open(pdf_path)
        for index, page in enumerate(doc):
            embedded = page.get_text("text")
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False
            )
            image = preprocess(Image.open(io.BytesIO(pixmap.tobytes("png"))))
            for engine_name, run_engine in (
                ("embedded", lambda: embedded),
                (
                    "tesseract",
                    lambda: " ".join(
                        word.text for word in TesseractEngine().run(image)
                    ),
                ),
                (
                    "paddleocr",
                    lambda: " ".join(word.text for word in PaddleEngine().run(image)),
                ),
            ):
                started = time.perf_counter()
                try:
                    output = run_engine()
                    elapsed = time.perf_counter() - started
                    reference = str(truth_pages.get(str(index + 1), ""))
                    wer, cer = (
                        _error_rates(reference, output) if reference else ("", "")
                    )
                    status = (
                        "measured" if reference else "no_transcription_ground_truth"
                    )
                except Exception as exc:
                    output, elapsed, wer, cer = (
                        "",
                        time.perf_counter() - started,
                        "",
                        "",
                    )
                    status = f"unavailable: {type(exc).__name__}"
                rows.append(
                    {
                        "file": pdf_path.name,
                        "page": index + 1,
                        "engine": engine_name,
                        "seconds": elapsed,
                        "characters": len(output),
                        "wer": wer,
                        "cer": cer,
                        "status": status,
                    }
                )
        doc.close()
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, default=Path("data/samples"))
    parser.add_argument("--ground-truth", type=Path, default=Path("data/ground_truth"))
    parser.add_argument("--files", nargs="*", help="Limit to named PDFs in --samples.")
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/results/ocr.csv")
    )
    args = parser.parse_args()
    rows = benchmark(args.samples, args.ground_truth, args.files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "file",
                "page",
                "engine",
                "seconds",
                "characters",
                "wer",
                "cer",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} per-engine page rows.")
