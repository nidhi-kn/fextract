"""Runtime configuration loaded from CLI options and environment."""

import os
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE settings without overriding process variables."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_dotenv()


def confidence_threshold(value: float | None = None) -> float:
    """Return a validated confidence threshold, honoring environment default."""
    selected = (
        value
        if value is not None
        else float(os.getenv("FEXTRACT_CONFIDENCE_THRESHOLD", "0.7"))
    )
    if not 0 <= selected <= 1:
        raise ValueError("confidence threshold must be between 0 and 1")
    return selected
