"""Group page labels into sections while avoiding weak false starts."""


def group_sections(
    labels: list[tuple[str, float]], min_start_confidence: float = 0.9
) -> list[dict[str, object]]:
    """Group consecutive page types; weak pages continue the prior section.

    A weak first page is conservatively labeled ``notes_other``. Later pages
    need the configured signal threshold to start a new document section.
    """
    if not labels:
        return []

    resolved: list[str] = []
    for label, confidence in labels:
        if confidence < min_start_confidence:
            resolved.append(resolved[-1] if resolved else "notes_other")
        else:
            resolved.append(label if label != "unknown" else "notes_other")

    result: list[dict[str, object]] = []
    evidence: list[list[float]] = []
    for page, label in enumerate(resolved, start=1):
        original_label, confidence = labels[page - 1]
        strong_signal = original_label == label and confidence >= min_start_confidence
        if not result or result[-1]["doc_type"] != label:
            result.append(
                {"doc_type": label, "doc_type_confidence": confidence, "pages": [page]}
            )
            evidence.append([confidence] if strong_signal else [])
        else:
            result[-1]["pages"].append(page)
            if strong_signal:
                evidence[-1].append(confidence)
            if evidence[-1]:
                result[-1]["doc_type_confidence"] = sum(evidence[-1]) / len(
                    evidence[-1]
                )
    return result
