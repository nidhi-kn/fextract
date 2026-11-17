"""Local Ollama availability and latency probe (no hosted API calls)."""

import csv
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request


def benchmark(models: list[str]) -> list[dict[str, object]]:
    """Query only the configured local Ollama daemon and report model status."""
    endpoint = (
        os.getenv("FEXTRACT_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        + "/api/generate"
    )
    rows = []
    for model in models:
        prompt = (
            'Extract invoice_number from this source text: "Invoice No: SYN-0042". '
            "Return only JSON with key invoice_number."
        )
        payload = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0},
            }
        ).encode()
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    endpoint, payload, {"Content-Type": "application/json"}
                ),
                timeout=120,
            ) as response:
                data = json.loads(response.read())
            output = data.get("response", "")
            try:
                parsed = json.loads(output)
                accuracy = parsed.get("invoice_number") == "SYN-0042"
            except (json.JSONDecodeError, AttributeError):
                accuracy = False
            rows.append(
                {
                    "model": model,
                    "seconds": time.perf_counter() - started,
                    "peak_ram_mb": "",
                    "field_exact_match": accuracy,
                    "status": "ok",
                    "response": output,
                }
            )
        except (urllib.error.URLError, TimeoutError) as exc:
            rows.append(
                {
                    "model": model,
                    "seconds": time.perf_counter() - started,
                    "peak_ram_mb": "",
                    "field_exact_match": "",
                    "status": f"unavailable: {exc}",
                    "response": "",
                }
            )
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="*", default=["qwen2.5:1.5b", "qwen2.5:3b"])
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/results/llm.csv")
    )
    args = parser.parse_args()
    rows = benchmark(args.models)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "model",
                "seconds",
                "peak_ram_mb",
                "field_exact_match",
                "status",
                "response",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} local model probe rows.")
