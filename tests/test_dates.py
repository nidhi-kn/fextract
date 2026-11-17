"""Date normalisation cases."""

import pytest
from fextract.normalize.dates import normalize_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("01/02/2024", "2024-02-01"),
        ("2024-02-01", "2024-02-01"),
        ("1-Feb-2024", "2024-02-01"),
        ("1 February 2024", "2024-02-01"),
        ("6th September,2022", "2022-09-06"),
        ("31st March, 2022", "2022-03-31"),
        ("31/12/23", "2023-12-31"),
        ("bad", None),
        (None, None),
    ],
)
def test_date_formats(raw, expected):
    assert normalize_date(raw) == expected
