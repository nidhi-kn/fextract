"""Number normalisation regression cases."""

import pytest
from fextract.normalize.numbers import normalize_number


@pytest.mark.parametrize(
    ("raw", "expected", "unit"),
    [
        ("46,12,930", 4612930, None),
        ("1,23,456.78", 123456.78, None),
        ("1,234,567", 1234567, None),
        ("(1,256.13)", -1256.13, None),
        ("1,256.13-", -1256.13, None),
        ("-1256.13", -1256.13, None),
        ("₹ 1,000", 1000, None),
        ("Rs. 250", 250, None),
        ("USD 99.5", 99.5, None),
        ("$12", 12, None),
        ("£1,234", 1234, None),
        ("€45.67", 45.67, None),
        ("2 lakhs", 200000, "lakhs"),
        ("1.5 crore", 15000000, "crores"),
        ("3 crores", 30000000, "crores"),
        ("4 thousand", 4000, "thousands"),
        ("(₹ 2 lakhs)", -200000, "lakhs"),
        ("-", None, None),
        ("—", None, None),
        ("", None, None),
        ("12.00", 12, None),
        ("Rs 46,12,930", 4612930, None),
        ("1,00,00,000", 10000000, None),
    ],
)
def test_number_cases(raw, expected, unit):
    result = normalize_number(raw)
    assert result.value == expected
    assert result.unit == unit
