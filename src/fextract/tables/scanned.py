"""Cluster OCR word boxes into rows and approximate columns."""


def cluster_words(
    words: list[dict[str, object]], y_tolerance: float = 8.0
) -> list[list[str]]:
    """Sort OCR word dictionaries into visual rows using their bounding boxes."""
    ordered = sorted(
        words, key=lambda word: (float(word["bbox"][1]), float(word["bbox"][0]))
    )
    rows: list[list[tuple[float, str]]] = []
    row_y: list[float] = []
    for word in ordered:
        x0, y0 = word["bbox"][0], word["bbox"][1]
        if not row_y or abs(float(y0) - row_y[-1]) > y_tolerance:
            rows.append([])
            row_y.append(float(y0))
        rows[-1].append((float(x0), str(word["text"])))
    return [[text for _, text in sorted(row)] for row in rows]
