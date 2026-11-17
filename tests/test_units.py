"""Fictional statement tests for unit detection and inherited provenance."""

from fextract.normalize.units import detect_unit, inherited_unit


def test_detects_multiplier_after_backtick_or_rupee_symbol():
    assert detect_unit("(All amounts in ` crores unless stated otherwise)") == "crores"
    assert detect_unit("(All amounts in ₹ lakhs)") == "lakhs"
    assert detect_unit("All figures in INR thousands") == "thousands"


def test_detects_plain_rupee_currency_without_multiplier():
    assert detect_unit("Amounts are stated in rupees") == "rupees"
    assert detect_unit("All amounts in Rs.") == "rupees"


def test_inherited_unit_has_lower_confidence_and_explicit_provenance():
    field = inherited_unit("lakhs", page=2)

    assert field.value == "lakhs"
    assert field.confidence == 0.6
    assert field.page == 2
    assert field.source == "derived"
    assert field.flags == ["inherited"]
