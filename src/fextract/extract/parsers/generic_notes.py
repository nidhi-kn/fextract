"""Conservative key/value capture for notes and other finance pages."""

import re


def parse_notes(text: str) -> tuple[dict[str, str], list[list[str]]]:
    """Capture simple labelled lines and tabular-looking text rows."""
    pairs, table = {}, []
    for line in text.splitlines():
        parts = re.split(r"\s{2,}|\s*:\s*", line.strip(), maxsplit=1)
        if len(parts) == 2 and len(parts[0]) < 80:
            pairs[parts[0].strip()] = parts[1].strip()
        if len(re.findall(r"\d", line)) >= 2:
            table.append(re.split(r"\s{2,}", line.strip()))
    return pairs, table
