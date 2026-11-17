"""Fault-tolerant parallel directory processing."""

from pathlib import Path
from joblib import Parallel, delayed
from fextract.ingest.loader import discover_files
from fextract.pipeline import extract_document


def process_batch(
    input_path: Path,
    workers: int = 1,
    threshold: float = 0.7,
    use_vlm: bool = False,
    use_llm: bool = False,
):
    """Process supported files independently; each failure becomes a result."""
    files, _ignored = discover_files(input_path)
    return Parallel(n_jobs=max(1, workers), prefer="processes")(
        delayed(extract_document)(path, threshold, use_vlm, use_llm) for path in files
    )
