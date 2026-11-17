"""Click command line interface for fextract."""

import json
from pathlib import Path
import click
from fextract.batch import process_batch
from fextract.config import confidence_threshold as get_confidence_threshold
from fextract.report import write_results


@click.group()
def main() -> None:
    """Extract auditable fields from local finance documents."""


@main.command()
@click.option(
    "--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True
)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--workers", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--format", "formats", default="json,csv", show_default=True)
@click.option("--confidence-threshold", type=click.FloatRange(0, 1), default=None)
@click.option(
    "--use-vlm", is_flag=True, help="Enable the optional local vision model hook."
)
@click.option(
    "--use-llm",
    is_flag=True,
    help="Use the configured local Ollama text model for missing fields.",
)
def run(
    input_path: Path,
    output: Path,
    workers: int,
    formats: str,
    confidence_threshold: float | None,
    use_vlm: bool,
    use_llm: bool,
) -> None:
    """Process a file or recursively process an input directory."""
    threshold = get_confidence_threshold(confidence_threshold)
    results = process_batch(input_path, workers, threshold, use_vlm, use_llm)
    write_results(
        results, output, {item.strip() for item in formats.split(",") if item.strip()}
    )
    click.echo(
        json.dumps(
            {
                "documents": len(results),
                "errors": sum(bool(item.errors) for item in results),
                "output": str(output),
            }
        )
    )


@main.command()
@click.option(
    "--ground-truth", type=click.Path(exists=True, path_type=Path), required=True
)
def benchmark(ground_truth: Path) -> None:
    """Run local evaluation against available labelled JSON files."""
    from fextract.evaluation import run_benchmark

    click.echo(json.dumps(run_benchmark(ground_truth), indent=2))


@main.command()
@click.argument("result_file", type=click.Path(exists=True, path_type=Path))
def inspect(result_file: Path) -> None:
    """Print a concise summary of one output JSON."""
    data = json.loads(result_file.read_text(encoding="utf-8"))
    click.echo(
        f"{data['source_file']}: {data['page_count']} pages, {len(data['sections'])} sections"
    )
    for section in data["sections"]:
        click.echo(
            f"  {section['doc_type']} pages={section['pages']} fields={len(section['fields'])}"
        )


if __name__ == "__main__":
    main()
