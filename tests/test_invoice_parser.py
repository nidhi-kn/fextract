"""Invoice parser regression tests."""

from fextract.extract.parsers.invoice import (
    merge_positioned_party_fallbacks,
    parse_invoice_address_words,
    parse_invoice_items,
    parse_invoice,
)


def test_invoice_extracts_number_date_and_total():
    fields = parse_invoice(
        "Invoice No: INV-123\nInvoice Date: 01/02/2024\nGrand Total: GBP 1,234.50"
    )
    assert fields["invoice_number"].value == "INV-123"
    assert fields["invoice_date"].value == "2024-02-01"
    assert fields["total_sales_value"].value == 1234.5


def test_party_names_support_varied_fictional_invoice_layouts():
    cases = [
        (
            "Northstar Instruments Ltd\n42 Orbit Road\nInvoice No: NS-8\n"
            "Bill To: Juniper Trading LLC\nInvoice Date: 01/02/2024",
            "Northstar Instruments Ltd",
            "Juniper Trading LLC",
        ),
        (
            "Seller: Blue Finch Components GmbH\nBuyer: Red Maple Systems Inc.\n"
            "Invoice Number: BF-42",
            "Blue Finch Components GmbH",
            "Red Maple Systems Inc",
        ),
        (
            "Supplier\nCopper Kite Manufacturing PLC\nShip To: Silver Meadow Labs Ltd\n"
            "Tax Invoice: CK-14",
            "Copper Kite Manufacturing PLC",
            "Silver Meadow Labs Ltd",
        ),
    ]

    for text, vendor, customer in cases:
        fields = parse_invoice(text)
        assert fields["vendor_name"].value == vendor
        assert fields["customer_name"].value == customer


def test_positioned_party_guess_does_not_replace_labeled_text_party():
    fields = parse_invoice(
        "COMMERCIAL INVOICE\nInvoice No: NK-14\n"
        "Vendor: Northstar Kiteworks Ltd\nGrand Total: USD 438.20"
    )

    merged = merge_positioned_party_fallbacks(
        fields,
        {
            "vendor_name": "Grand Total USD 438.20",
            "customer_name": "Juniper Harbor Supply LLC",
            "consignor_address": "Northstar Kiteworks Ltd, 8 Lantern Way",
        },
        page=1,
    )

    assert merged["vendor_name"].value == "Northstar Kiteworks Ltd"
    assert merged["customer_name"].value == "Juniper Harbor Supply LLC"
    assert merged["consignor_address"].value == "Northstar Kiteworks Ltd, 8 Lantern Way"


def test_ocr_party_label_accepts_separator_noise_and_supplier_name_is_not_a_heading():
    fields = parse_invoice(
        "COMMERCIAL INVOICE\nVendor; Example Supplier 3\nGrand Total: USD 808.17"
    )
    words = [
        {"text": "Vendor;", "x0": 10, "x1": 45, "top": 100, "bottom": 110},
        {"text": "Example", "x0": 50, "x1": 90, "top": 100, "bottom": 110},
        {"text": "Supplier", "x0": 95, "x1": 145, "top": 100, "bottom": 110},
        {"text": "3", "x0": 150, "x1": 155, "top": 100, "bottom": 110},
    ]

    assert fields["vendor_name"].value == "Example Supplier 3"
    assert parse_invoice_address_words(words) == {}


def test_invoice_description_wrapped_before_kit_quantity_is_merged():
    rows = parse_invoice_items(
        {
            1: [
                [
                    [
                        "2401-001 K100/1 AUR-100 Asterion Calibration Module\n"
                        "Bundle KIT 1 12.50 2 25.00 25.00"
                    ]
                ]
            ]
        },
        [1],
    )

    assert len(rows) == 1
    assert rows[0]["description"] == "Asterion Calibration Module Bundle KIT 1"
