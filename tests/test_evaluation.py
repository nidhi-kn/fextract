"""Evaluation behavior for partially and fully labelled documents."""

import json

from fextract.schemas import DocumentResult, FieldValue, SectionResult
import fextract.evaluation as evaluation


def _prediction() -> DocumentResult:
    """Return fictional extraction with one unlabelled extra prediction."""
    return DocumentResult(
        source_file="fixture.pdf",
        page_count=1,
        extraction_paths={1: "digital_text"},
        sections=[
            SectionResult(
                doc_type="commercial_invoice",
                doc_type_confidence=0.99,
                pages=[1],
                fields={
                    "invoice_number": FieldValue(value="FICTION-44"),
                    "vendor_name": FieldValue(value="Acme Fiction Ltd"),
                },
            )
        ],
    )


def _ground_truth_tree(tmp_path, fields):
    truth_dir = tmp_path / "data" / "ground_truth"
    truth_dir.mkdir(parents=True)
    (tmp_path / "data" / "samples").mkdir()
    (truth_dir / "fixture.json").write_text(
        json.dumps(
            {
                "source_file": "fixture.pdf",
                "verified": True,
                "fields": fields,
            }
        ),
        encoding="utf-8",
    )
    return truth_dir


def test_partial_labels_report_verified_accuracy_and_ignore_unlabelled_extras(
    tmp_path, monkeypatch
):
    truth_dir = _ground_truth_tree(
        tmp_path,
        {
            "invoice_number": {"value": "FICTION-44", "verified": True},
            "total_sales_value": {"value": 120.0, "verified": True},
        },
    )
    monkeypatch.setattr(
        evaluation, "process_batch", lambda *args, **kwargs: [_prediction()]
    )

    result = evaluation.run_benchmark(truth_dir)

    assert result["verified_fields"] == 2
    assert result["correct_fields"] == 1
    assert result["accuracy"] == 0.5
    assert result["precision"] is None
    assert result["recall"] is None
    assert result["f1"] is None
    assert result["per_document"]["fixture.pdf"]["unlabelled_predictions"] == 0


def test_fully_labelled_ground_truth_keeps_precision_recall_and_f1(
    tmp_path, monkeypatch
):
    truth_dir = _ground_truth_tree(
        tmp_path,
        {
            "invoice_number": "FICTION-44",
        },
    )
    truth_path = truth_dir / "fixture.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth.pop("verified")
    truth["fields"] = {"invoice_number": "FICTION-44"}
    truth_path.write_text(json.dumps(truth), encoding="utf-8")
    monkeypatch.setattr(
        evaluation, "process_batch", lambda *args, **kwargs: [_prediction()]
    )

    result = evaluation.run_benchmark(truth_dir)

    assert result["precision"] == 0.5
    assert result["recall"] == 1.0
    assert result["f1"] == 2 / 3
