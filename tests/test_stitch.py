"""Multi-page table stitching tests."""

from fextract.tables.stitch import stitch_tables


def test_repeated_headers_are_removed():
    assert stitch_tables(
        [[["date", "amount"], ["01/01", "5"]], [["date", "amount"], ["02/01", "6"]]]
    ) == [["date", "amount"], ["01/01", "5"], ["02/01", "6"]]
