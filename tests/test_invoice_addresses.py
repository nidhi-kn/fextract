"""Synthetic column geometry regression for invoice addresses."""

from fextract.extract.parsers.invoice import parse_invoice_address_words


def test_address_blocks_are_split_by_x_position():
    tokens = [
        ("Consignor", 10, 10),
        ("Supplier", 10, 20),
        ("1", 10, 30),
        ("West", 20, 30),
        ("Consignee", 200, 10),
        ("Buyer", 200, 20),
        ("2", 200, 30),
        ("East", 210, 30),
        ("Delivery", 400, 10),
        ("Address", 450, 10),
        ("Receiver", 400, 20),
        ("3", 400, 30),
        ("South", 410, 30),
        ("Item", 10, 100),
        ("Code", 30, 100),
        ("Description", 60, 100),
        ("Price", 140, 100),
        ("Qty", 190, 100),
        ("Amount", 230, 100),
        ("Tax", 300, 100),
        ("Total", 350, 100),
    ]
    words = [{"text": text, "x0": x, "x1": x + 10, "top": y} for text, x, y in tokens]
    fields = parse_invoice_address_words(words)
    assert fields == {
        "consignor_address": "Supplier 1 West",
        "consignee_address": "Buyer 2 East",
        "delivery_address": "Receiver 3 South",
    }
