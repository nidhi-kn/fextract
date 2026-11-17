"""Stitch consecutive page tables and remove repeated headers."""


def stitch_tables(tables: list[list[list[str]]]) -> list[list[str]]:
    """Join compatible tables, discard repeated header rows, preserve row order."""
    output: list[list[str]] = []
    header: list[str] | None = None
    for table in tables:
        rows = [[str(cell or "").strip() for cell in row] for row in table if row]
        if not rows:
            continue
        if header is None:
            header = rows[0]
            output.extend(rows)
            continue
        if len(rows[0]) == len(header) and [v.lower() for v in rows[0]] == [
            v.lower() for v in header
        ]:
            rows = rows[1:]
        elif len(rows[0]) != len(header):
            output.extend(rows)
            continue
        for row in rows:
            if (
                output
                and header is not None
                and len(row) == len(header)
                and not row[0].strip()
                and len(output[-1]) == len(row)
            ):
                output[-1] = [
                    " ".join(part for part in (prior, current) if part).strip()
                    for prior, current in zip(output[-1], row)
                ]
            else:
                output.append(row)
    return output
