"""Field-level exact-match benchmark against hand-labelled JSON fixtures."""

from pathlib import Path
from fextract.evaluation import run_benchmark

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path, default=Path("data/ground_truth"))
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/results/pipeline.csv")
    )
    args = parser.parse_args()
    import time

    results = []
    for workers in (1, 2, 4):
        if any(
            '"verified": false' in path.read_text(encoding="utf-8").lower()
            for path in args.ground_truth.glob("Document*.json")
        ) and not any(
            '"verified": true' in path.read_text(encoding="utf-8").lower()
            for path in args.ground_truth.glob("Document*.json")
        ):
            result = run_benchmark(args.ground_truth, workers=workers)
            result["seconds"] = ""
            result["documents_per_second"] = ""
            results.append(result)
            continue
        started = time.perf_counter()
        result = run_benchmark(args.ground_truth, workers=workers)
        elapsed = time.perf_counter() - started
        result["seconds"] = elapsed
        result["documents_per_second"] = (
            result["documents"] / elapsed if elapsed else 0.0
        )
        results.append(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import csv

    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(results)
