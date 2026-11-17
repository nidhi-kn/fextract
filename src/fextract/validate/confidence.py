"""Transparent confidence scoring and review flagging."""


def score_confidence(
    source_score: float, agreement_score: float, validation_score: float
) -> float:
    """Compute the documented weighted confidence score."""
    return max(
        0.0,
        min(1.0, 0.4 * source_score + 0.3 * agreement_score + 0.3 * validation_score),
    )


def flag_fields(
    fields, validations, threshold: float = 0.7, source_score: float = 1.0
) -> list[str]:
    """Flag only missing, low-confidence, disagreed, or validation-bound fields."""
    review = []
    related_fields = {
        "assets_equal_liabilities": {"total_assets", "total_liabilities"},
        "income_less_expenses_equals_profit_before_tax": {
            "revenue",
            "other_income",
            "expenses",
            "exceptional_items",
            "profit_before_tax",
        },
        "profit_before_tax_less_tax_equals_profit": {
            "profit_before_tax",
            "tax_expense",
            "profit",
        },
        "opening_plus_change_equals_closing": {
            "opening_cash",
            "net_change",
            "closing_cash",
        },
        "prior_year_opening_plus_change_equals_closing": {
            "opening_cash_prior_year",
            "net_change_prior_year",
            "closing_cash_prior_year",
        },
        "activities_sum_equals_net_change": {
            "operating_activities",
            "investing_activities",
            "financing_activities",
            "net_change",
        },
        "line_sales_sum_equals_invoice_total": {"total_sales_value"},
        "invoice_item_quantity_times_price": {"total_sales_value"},
        "running_balance": {"opening_balance", "closing_balance"},
    }
    failed_fields = set()
    passed_fields = set()
    for result in validations:
        bound = related_fields.get(result.check, set())
        if result.passed is False:
            failed_fields.update(bound)
        elif result.passed is True:
            passed_fields.update(bound)
    for name, item in fields.items():
        field_source_score = source_score
        if item.source in {"llm", "vlm"}:
            field_source_score = min(source_score, 0.75)
        if item.source == "none":
            field_source_score = 0.0
        agreement_score = (
            0.0
            if "source_disagreement" in item.flags
            else 1.0 if "sources_agree" in item.flags else 0.5
        )
        validation_score = (
            0.0 if name in failed_fields else 1.0 if name in passed_fields else 0.5
        )
        item.confidence = score_confidence(
            field_source_score, agreement_score, validation_score
        )
        if item.value is None:
            item.confidence = 0.0
        if (
            item.value is None
            or item.confidence < threshold
            or "source_disagreement" in item.flags
            or name in failed_fields
        ):
            if "review" not in item.flags:
                item.flags.append("review")
            review.append(name)
        if name in failed_fields and "validation_failed" not in item.flags:
            item.flags.append("validation_failed")
    return review
