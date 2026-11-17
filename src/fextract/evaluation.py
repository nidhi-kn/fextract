"""Ground-truth evaluation shared by the CLI and benchmark script."""

import json
from pathlib import Path
from typing import Any
from fextract.batch import process_batch


def run_benchmark(ground_truth: Path, workers: int = 1) -> dict[str, Any]:
    """Evaluate verified fields without treating unlabelled predictions as errors."""
    truth_paths = sorted(ground_truth.glob("*.json"))
    truths, source_dir = {}, None
    partial_labels = False
    for truth_path in truth_paths:
        if truth_path.name == "template.json" or truth_path.name.endswith(".ocr.json"):
            continue
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        partial_labels = partial_labels or truth.get("verified") is True
        source_file = truth.get("source_file", f"{truth_path.stem}.pdf")
        verified = {}
        if truth.get("verified") is not False:
            if "sections" in truth:
                for section_index, section in enumerate(truth["sections"], start=1):
                    for name, expected in section.get("fields", {}).items():
                        if (
                            isinstance(expected, dict)
                            and expected.get("verified") is True
                        ):
                            verified[f"section_{section_index}.{name}"] = expected.get(
                                "value"
                            )
            else:
                for name, expected in truth.get("fields", {}).items():
                    if isinstance(expected, dict) and "value" in expected:
                        if expected.get("verified") is True:
                            verified[name] = expected["value"]
                    else:
                        # Legacy generated fixtures contain generator-known values.
                        verified[name] = expected
        truths[source_file] = verified
        candidate = truth_path.parent.parent / "samples"
        if candidate.exists():
            source_dir = candidate
    if not truths or source_dir is None:
        return {
            "status": "no_ground_truth_or_source",
            "documents": 0,
            "precision": None,
            "recall": None,
            "f1": None,
            "flag_precision": None,
            "flag_recall": None,
            "workers": workers,
        }
    verified_count = sum(len(fields) for fields in truths.values())
    if not verified_count:
        return {
            "status": "no_verified_ground_truth",
            "documents": len(truths),
            "precision": None,
            "recall": None,
            "f1": None,
            "flag_precision": None,
            "flag_recall": None,
            "workers": workers,
            "verified_fields": 0,
            "correct_fields": 0,
            "accuracy": None,
            "per_document": {},
        }
    results = process_batch(source_dir, workers=workers)
    predicted, predicted_flags = {}, {}
    for document in results:
        predicted[document.source_file] = {}
        predicted_flags[document.source_file] = set()
        for section_index, section in enumerate(document.sections, start=1):
            for name, item in section.fields.items():
                qualified = f"section_{section_index}.{name}"
                if item.value is not None:
                    predicted[document.source_file][qualified] = item.value
                    predicted[document.source_file][name] = item.value
                if "review" in item.flags:
                    predicted_flags[document.source_file].update({qualified, name})
    tp = fp = fn = 0
    flag_tp = flag_fp = flag_fn = 0
    correct_fields = 0
    per_document = {}
    for filename, expected in truths.items():
        actual_all = predicted.get(filename, {})
        flags_all = predicted_flags.get(filename, set())
        qualified_truth = any(name.startswith("section_") for name in expected)
        actual = {
            name: value
            for name, value in actual_all.items()
            if name.startswith("section_") == qualified_truth
        }
        flags = {
            name for name in flags_all if name.startswith("section_") == qualified_truth
        }
        document_correct = 0
        document_mismatches = []
        for name, value in expected.items():
            correct = name in actual and actual[name] == value
            if correct:
                tp += 1
                correct_fields += 1
                document_correct += 1
            else:
                fn += 1
                document_mismatches.append(name)
            flagged = name in flags
            if flagged and not correct:
                flag_tp += 1
            elif flagged and correct:
                flag_fp += 1
            elif not flagged and not correct:
                flag_fn += 1
        document_fp = sum(name not in expected for name in actual)
        fp += document_fp
        per_document[filename] = {
            "verified_fields": len(expected),
            "correct_fields": document_correct,
            "accuracy": document_correct / len(expected) if expected else None,
            "mismatches": document_mismatches,
            "unlabelled_predictions": 0 if partial_labels else document_fp,
        }
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    output = {
        "status": "ok",
        "documents": len(results),
        "precision": None if partial_labels else precision,
        "recall": None if partial_labels else recall,
        "f1": (
            None
            if partial_labels
            else (
                2 * precision * recall / (precision + recall)
                if precision + recall
                else 0.0
            )
        ),
        "flag_precision": flag_tp / (flag_tp + flag_fp) if flag_tp + flag_fp else 0.0,
        "flag_recall": flag_tp / (flag_tp + flag_fn) if flag_tp + flag_fn else 0.0,
        "workers": workers,
        "verified_fields": verified_count,
        "correct_fields": correct_fields,
        "accuracy": correct_fields / verified_count,
    }
    if partial_labels:
        output["per_document"] = per_document
    return output
