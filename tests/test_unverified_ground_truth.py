"""Unverified starter values must not count as benchmark labels."""

import json

from fextract.evaluation import run_benchmark


def test_unverified_values_are_excluded_from_accuracy(tmp_path):
    """A sample template with verified=false yields no accuracy estimate."""
    truth_dir = tmp_path / "ground_truth"
    truth_dir.mkdir()
    (tmp_path / "samples").mkdir()
    (truth_dir / "Document1.json").write_text(
        json.dumps(
            {
                "source_file": "Document1.pdf",
                "verified": False,
                "fields": {"invoice_number": {"value": "SYN-1", "verified": False}},
            }
        ),
        encoding="utf-8",
    )

    result = run_benchmark(truth_dir)

    assert result["status"] == "no_verified_ground_truth"
    assert result["verified_fields"] == 0
    assert result["precision"] is None
    assert result["flag_recall"] is None
