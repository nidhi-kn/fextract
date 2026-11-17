"""Arithmetic validation for common financial statement invariants."""

from math import isclose
from fextract.schemas import ValidationResult


def validate_section(doc_type: str, fields, tables) -> list[ValidationResult]:
    """Run checks supported by values actually extracted; missing inputs are unevaluable."""

    def val(key):
        item = fields.get(key)
        return item.value if item else None

    checks = []
    if doc_type == "commercial_invoice":
        items = tables.get("line_items", [])
        total = val("total_sales_value")
        item_sum = sum(float(row.get("sales_value") or 0) for row in items)
        checks.append(
            ValidationResult(
                check="line_sales_sum_equals_invoice_total",
                passed=(
                    None
                    if total is None or not items
                    else isclose(item_sum, float(total), abs_tol=0.02)
                ),
                detail=f"line_sum={item_sum}, total={total}, items={len(items)}",
            )
        )
        valid_rows = [
            row
            for row in items
            if row.get("qty") is not None
            and row.get("unit_price") is not None
            and row.get("sales_value") is not None
        ]
        checks.append(
            ValidationResult(
                check="invoice_item_quantity_times_price",
                passed=(
                    None
                    if not valid_rows
                    else all(
                        isclose(
                            float(row["qty"]) * float(row["unit_price"]),
                            float(row["sales_value"]),
                            abs_tol=0.02,
                        )
                        for row in valid_rows
                    )
                ),
                detail=f"validated={len(valid_rows)}, items={len(items)}",
            )
        )
    elif doc_type == "balance_sheet":
        left, right = val("total_assets"), val("total_liabilities")
        checks.append(
            ValidationResult(
                check="assets_equal_liabilities",
                passed=(
                    None
                    if left is None or right is None
                    else isclose(float(left), float(right), abs_tol=0.01)
                ),
                detail=f"assets={left}, liabilities={right}",
            )
        )
    elif doc_type == "profit_and_loss":
        revenue, other_income, expenses, exceptional, profit_before_tax = (
            val("revenue"),
            val("other_income"),
            val("expenses"),
            val("exceptional_items"),
            val("profit_before_tax"),
        )
        checks.append(
            ValidationResult(
                check="income_less_expenses_equals_profit_before_tax",
                passed=(
                    None
                    if None
                    in (revenue, other_income, expenses, exceptional, profit_before_tax)
                    else isclose(
                        float(revenue)
                        + float(other_income)
                        - float(expenses)
                        + float(exceptional),
                        float(profit_before_tax),
                        abs_tol=0.02,
                    )
                ),
                detail=(
                    f"revenue={revenue}, other_income={other_income}, "
                    f"expenses={expenses}, exceptional_items={exceptional}, "
                    f"profit_before_tax={profit_before_tax}"
                ),
            )
        )
        tax_expense, profit = (
            val("tax_expense"),
            val("profit"),
        )
        checks.append(
            ValidationResult(
                check="profit_before_tax_less_tax_equals_profit",
                passed=(
                    None
                    if None in (profit_before_tax, tax_expense, profit)
                    else isclose(
                        float(profit_before_tax) + float(tax_expense),
                        float(profit),
                        abs_tol=0.02,
                    )
                ),
                detail=(
                    f"profit_before_tax={profit_before_tax}, "
                    f"tax_expense={tax_expense}, profit={profit}"
                ),
            )
        )
    elif doc_type == "cash_flow_statement":
        opening, change, closing = (
            val("opening_cash"),
            val("net_change"),
            val("closing_cash"),
        )
        checks.append(
            ValidationResult(
                check="opening_plus_change_equals_closing",
                passed=(
                    None
                    if None in (opening, change, closing)
                    else isclose(
                        float(opening) + float(change), float(closing), abs_tol=0.01
                    )
                ),
            )
        )
        opening_prior = val("opening_cash_prior_year")
        change_prior = val("net_change_prior_year")
        closing_prior = val("closing_cash_prior_year")
        if any(
            value is not None for value in (opening_prior, change_prior, closing_prior)
        ):
            checks.append(
                ValidationResult(
                    check="prior_year_opening_plus_change_equals_closing",
                    passed=(
                        None
                        if None in (opening_prior, change_prior, closing_prior)
                        else isclose(
                            float(opening_prior) + float(change_prior),
                            float(closing_prior),
                            abs_tol=0.02,
                        )
                    ),
                )
            )
        operating, investing, financing = (
            val("operating_activities"),
            val("investing_activities"),
            val("financing_activities"),
        )
        checks.append(
            ValidationResult(
                check="activities_sum_equals_net_change",
                passed=(
                    None
                    if None in (operating, investing, financing, change)
                    else isclose(
                        float(operating) + float(investing) + float(financing),
                        float(change),
                        abs_tol=0.02,
                    )
                ),
                detail=f"A={operating}, B={investing}, C={financing}, net={change}",
            )
        )
    elif doc_type == "bank_statement":
        rows = tables.get("transactions", [])
        dates = [row.get("txn_date") for row in rows]
        monotonic = all(a <= b for a, b in zip(dates, dates[1:]) if a and b)
        checks.append(
            ValidationResult(
                check="transaction_dates_nondecreasing",
                passed=monotonic if dates else None,
            )
        )
        opening = val("opening_balance")
        previous = opening
        evaluable = bool(rows) and opening is not None
        balance_ok = True
        for row in rows:
            debit, credit, balance = (
                row.get("debit"),
                row.get("credit"),
                row.get("balance"),
            )
            if previous is None or balance is None or debit is None and credit is None:
                evaluable = False
                previous = balance
                continue
            expected = float(previous) - float(debit or 0) + float(credit or 0)
            balance_ok = balance_ok and isclose(expected, float(balance), abs_tol=0.01)
            previous = balance
        checks.append(
            ValidationResult(
                check="running_balance", passed=(balance_ok if evaluable else None)
            )
        )
    return checks
