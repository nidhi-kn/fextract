"""One-document finance extraction pipeline."""

from pathlib import Path
from time import perf_counter
import io

from fextract.classify.page_classifier import classify_page_sources, has_finance_signal
from fextract.classify.sections import group_sections
from fextract.extract.rules import extract_fields
from fextract.ingest.loader import load_pdf
from fextract.ingest.triage import (
    choose_text_source,
    score_text,
    text_quality_score,
)
from fextract.schemas import DocumentResult, SectionResult
from fextract.validate.checks import validate_section
from fextract.validate.cross_section import validate_cross_sections
from fextract.validate.confidence import flag_fields
from fextract.normalize.units import detect_unit, inherited_unit


def extract_document(
    path: str | Path,
    threshold: float = 0.7,
    use_vlm: bool = False,
    use_llm: bool = False,
) -> DocumentResult:
    """Extract a PDF or image file, returning an error result instead of raising."""
    path = Path(path)
    started = perf_counter()
    processing_errors = []

    def words_for_page(page_id: int):
        """Return positioned words from the source layer selected for a page."""
        if paths.get(page_id) == "ocr":
            return positioned_ocr_words.get(page_id, [])
        if path.suffix.lower() == ".pdf":
            from fextract.tables.digital import extract_page_words

            return extract_page_words(str(path), page_id - 1)
        return positioned_ocr_words.get(page_id, [])

    try:
        if path.stat().st_size == 0:
            raise ValueError("empty file")
        if path.suffix.lower() == ".pdf":
            pdf = load_pdf(path)
            pages, paths, page_tables, source_scores, source_quality = (
                [],
                {},
                {},
                {},
                {},
            )
            positioned_ocr_words = {}
            embedded_pages = []
            for index, page in enumerate(pdf):
                text = page.get_text("text")
                embedded_pages.append(text)
                image_area = any(
                    rect.width * rect.height > page.rect.width * page.rect.height * 0.65
                    for item in page.get_images(full=True)
                    for rect in page.get_image_rects(item[0])
                )
                triage = score_text(text, index + 1, image_area)
                # Full-page image pages are compared against fresh OCR even if
                # their embedded OCR layer looks superficially plausible.
                if (
                    triage.decision in {"ocr", "hybrid"} and text.strip()
                ) or image_area:
                    try:
                        from fextract.ocr.paddle_engine import PaddleEngine
                        from fextract.ocr.tesseract_engine import TesseractEngine
                        from fextract.ocr.preprocess import preprocess

                        pix = page.get_pixmap(
                            matrix=__import__("fitz").Matrix(300 / 72, 300 / 72),
                            alpha=False,
                        )
                        from PIL import Image

                        image = preprocess(Image.open(io.BytesIO(pix.tobytes("png"))))
                        try:
                            words = TesseractEngine().run(image)
                        except Exception as tess_error:
                            try:
                                words = PaddleEngine().run(image)
                            except Exception as paddle_error:
                                processing_errors.append(
                                    f"OCR unavailable on page {index + 1}: Tesseract: {tess_error}; PaddleOCR: {paddle_error}"
                                )
                                words = []
                        # Preserve OCR row structure for statement parsers.
                        ordered_words = sorted(
                            words, key=lambda word: (word.bbox[1], word.bbox[0])
                        )
                        rows = []
                        for word in ordered_words:
                            y = (word.bbox[1] + word.bbox[3]) / 2
                            if not rows or abs(rows[-1][0] - y) > 18:
                                rows.append((y, [word]))
                            else:
                                rows[-1][1].append(word)
                        ocr_text = "\n".join(
                            " ".join(
                                word.text
                                for word in sorted(row, key=lambda word: word.bbox[0])
                            )
                            for _, row in rows
                        )
                        source_scores[index + 1] = (
                            sum(word.confidence for word in words) / len(words)
                            if words
                            else 0.0
                        )
                        positioned_ocr_words[index + 1] = [
                            {
                                "text": word.text,
                                "x0": word.bbox[0],
                                "x1": word.bbox[2],
                                "top": word.bbox[1],
                                "bottom": word.bbox[3],
                            }
                            for word in words
                        ]
                        ocr_score = score_text(ocr_text, index + 1)
                        embedded_quality = text_quality_score(
                            triage.dictionary_ratio, triage.garbage_ratio
                        )
                        ocr_quality = text_quality_score(
                            ocr_score.dictionary_ratio,
                            ocr_score.garbage_ratio,
                            source_scores[index + 1],
                        )
                        source_quality[index + 1] = {
                            "embedded": embedded_quality,
                            "ocr": ocr_quality,
                            "embedded_dictionary_ratio": triage.dictionary_ratio,
                            "ocr_dictionary_ratio": ocr_score.dictionary_ratio,
                            "ocr_word_confidence": source_scores[index + 1],
                        }
                        if words:
                            from fextract.extract.rules import (
                                extract_fields as extract_candidate_fields,
                            )

                            candidate_type, _ = classify_page_sources((text, ocr_text))

                            def candidate_validation(candidate_text):
                                candidate_fields, candidate_tables = (
                                    extract_candidate_fields(
                                        candidate_type, candidate_text, index + 1
                                    )
                                )
                                return [
                                    result.passed
                                    for result in validate_section(
                                        candidate_type,
                                        candidate_fields,
                                        candidate_tables,
                                    )
                                ]

                            chosen_source = choose_text_source(
                                text,
                                ocr_text,
                                embedded_quality,
                                ocr_quality,
                                candidate_validation(text),
                                candidate_validation(ocr_text),
                            )
                        else:
                            chosen_source = (
                                "embedded_text" if text.strip() else "ocr_unavailable"
                            )
                        if chosen_source == "ocr":
                            text = ocr_text
                            paths[index + 1] = "ocr"
                        else:
                            paths[index + 1] = (
                                "digital_text"
                                if chosen_source == "embedded_text"
                                else "ocr_unavailable"
                            )
                        source_quality.setdefault(
                            index + 1,
                            {
                                "embedded": text_quality_score(
                                    triage.dictionary_ratio, triage.garbage_ratio
                                ),
                                "ocr": 0.0,
                                "embedded_dictionary_ratio": triage.dictionary_ratio,
                                "ocr_dictionary_ratio": 0.0,
                                "ocr_word_confidence": 0.0,
                            },
                        )
                    except Exception as exc:
                        processing_errors.append(
                            f"OCR failed on page {index + 1}: {exc}"
                        )
                        paths[index + 1] = "digital_text" if text else "ocr_unavailable"
                if paths.get(index + 1) != "ocr":
                    try:
                        from fextract.tables.digital import extract_page_tables

                        page_tables[index + 1] = extract_page_tables(str(path), index)
                    except Exception:
                        page_tables[index + 1] = []
                else:
                    page_tables[index + 1] = []
                if index + 1 not in source_scores:
                    source_scores[index + 1] = (
                        0.0 if paths.get(index + 1) == "ocr_unavailable" else 1.0
                    )
                if index + 1 not in paths:
                    paths[index + 1] = "digital_text"
                if not text.strip():
                    paths[index + 1] = "blank"
                pages.append(text)
            page_count = len(pages)
            pdf.close()
        else:
            from PIL import Image

            image = Image.open(path).convert("RGB")
            text, page_count, paths, page_tables, source_scores = (
                "",
                1,
                {1: "ocr"},
                {},
                {1: 0.0},
            )
            source_quality = {}
            from fextract.ocr.tesseract_engine import TesseractEngine

            words = TesseractEngine().run(image)
            positioned_ocr_words = {
                1: [
                    {
                        "text": word.text,
                        "x0": word.bbox[0],
                        "x1": word.bbox[2],
                        "top": word.bbox[1],
                        "bottom": word.bbox[3],
                    }
                    for word in words
                ]
            }
            source_scores[1] = (
                sum(word.confidence for word in words) / len(words) if words else 0.0
            )
            text = _ocr_words_to_lines(words)
            if not text.strip():
                paths[1] = "blank"
            pages = [text]
            embedded_pages = [""]
        labels = [
            classify_page_sources((embedded, selected))
            for embedded, selected in zip(embedded_pages, pages)
        ]
        grouped = group_sections(labels)
        if not any(has_finance_signal(text) for text in pages):
            grouped = [
                {
                    "doc_type": "unknown",
                    "doc_type_confidence": 0.0,
                    "pages": list(range(1, page_count + 1)),
                }
            ]
        unit_evidence = [
            (page_id, unit)
            for page_id, text in enumerate(pages, start=1)
            if (unit := detect_unit(text)) is not None
        ]
        distinct_units = {unit for _, unit in unit_evidence}
        document_unit = next(iter(distinct_units)) if len(distinct_units) == 1 else None
        unit_page = next(
            (page_id for page_id, unit in unit_evidence if unit == document_unit), None
        )
        sections, needs_review = [], []
        for group in grouped:
            page_ids = group["pages"]
            text = "\n".join(pages[index - 1] for index in page_ids)
            parse_text = text
            fields, tables = extract_fields(group["doc_type"], parse_text, page_ids[0])
            if group["doc_type"] == "bank_statement":
                from fextract.extract.parsers.bank_statement import (
                    parse_bank_table_pages,
                    parse_bank_positioned_pages,
                )

                fields, transactions = parse_bank_table_pages(page_tables, page_ids)
                if not transactions:
                    positioned = {
                        page_id: words_for_page(page_id) for page_id in page_ids
                    }
                    fields, transactions = parse_bank_positioned_pages(
                        positioned, page_ids
                    )
                tables = {"transactions": transactions}
            elif group["doc_type"] == "balance_sheet":
                from fextract.extract.parsers.balance_sheet import (
                    parse_balance_sheet_totals_words,
                )

                for page_id in page_ids:
                    positioned = words_for_page(page_id)
                    fields.update(parse_balance_sheet_totals_words(positioned, page_id))
            elif group["doc_type"] == "profit_and_loss":
                from fextract.extract.parsers.profit_loss import (
                    parse_profit_loss_positioned,
                )

                for page_id in page_ids:
                    fields.update(
                        parse_profit_loss_positioned(words_for_page(page_id), page_id)
                    )
            elif group["doc_type"] == "cash_flow_statement":
                from fextract.extract.parsers.cash_flow import (
                    parse_cash_flow_positioned,
                )

                fields.update(
                    parse_cash_flow_positioned(
                        {page_id: words_for_page(page_id) for page_id in page_ids}
                    )
                )
            elif group["doc_type"] == "commercial_invoice":
                from fextract.extract.parsers.invoice import (
                    merge_positioned_party_fallbacks,
                    parse_invoice_addresses,
                    parse_invoice_party_words,
                    parse_invoice_items,
                )

                rows = parse_invoice_items(page_tables, page_ids)
                if rows:
                    tables["line_items"] = rows
                first_words = words_for_page(page_ids[0])
                party_fields = parse_invoice_party_words(first_words)
                if path.suffix.lower() == ".pdf":
                    party_fields.update(
                        parse_invoice_addresses(str(path), page_ids[0] - 1)
                    )
                fields = merge_positioned_party_fallbacks(
                    fields, party_fields, page_ids[0]
                )
            if (
                document_unit
                and group["doc_type"]
                in {"balance_sheet", "profit_and_loss", "cash_flow_statement"}
                and (fields.get("unit") is None or fields["unit"].value is None)
            ):
                fields["unit"] = inherited_unit(document_unit, unit_page or page_ids[0])
            if use_llm:
                from fextract.extract.llm import extract_missing_fields

                missing = [name for name, item in fields.items() if item.value is None]
                if missing:
                    try:
                        llm_values = extract_missing_fields(text, missing)
                        # A second, narrow prompt avoids role confusion between
                        # an audit firm and the audited entity on scanned reports.
                        if (
                            group["doc_type"] == "audit_report"
                            and "auditor_firm" in missing
                            and "auditor_firm" not in llm_values
                            and "chartered accountant" in text.casefold()
                        ):
                            source_lines = text.splitlines()
                            firm_context = "\n".join(
                                line
                                for index, line in enumerate(source_lines)
                                if "chartered accountant" in line.casefold()
                                for line in source_lines[max(0, index - 1) : index + 2]
                            )
                            llm_values.update(
                                extract_missing_fields(firm_context, ["auditor_firm"])
                            )
                        for name, value in llm_values.items():
                            from fextract.schemas import FieldValue
                            from fextract.normalize.dates import normalize_date
                            from fextract.normalize.numbers import normalize_number

                            if name.endswith("_date") or name in {
                                "period_start",
                                "period_end",
                                "as_on_date",
                            }:
                                value = normalize_date(str(value)) or value
                            elif name in {
                                "total_sales_value",
                                "freight_value",
                                "total_net_weight",
                                "total_assets",
                                "total_liabilities",
                                "opening_balance",
                                "closing_balance",
                                "net_change",
                                "opening_cash",
                                "closing_cash",
                            }:
                                value = normalize_number(value).value

                            fields[name] = FieldValue(
                                value=value,
                                confidence=0.5,
                                page=page_ids[0],
                                source="llm",
                            )
                    except Exception as exc:
                        processing_errors.append(
                            f"LLM unavailable for section {page_ids}: {exc}"
                        )
            if use_vlm:
                missing = [name for name, item in fields.items() if item.value is None]
                if missing and any(
                    paths.get(p) in {"ocr", "ocr_unavailable"} for p in page_ids
                ):
                    try:
                        import fitz
                        from PIL import Image
                        from fextract.extract.vlm import extract_from_image

                        with fitz.open(path) as vlm_pdf:
                            for p in page_ids:
                                if paths.get(p) not in {"ocr", "ocr_unavailable"}:
                                    continue
                                pix = vlm_pdf[p - 1].get_pixmap(
                                    matrix=fitz.Matrix(1.5, 1.5), alpha=False
                                )
                                image = Image.open(io.BytesIO(pix.tobytes("png")))
                                for name, value in extract_from_image(
                                    image, missing, pages[p - 1]
                                ).items():
                                    from fextract.schemas import FieldValue

                                    fields[name] = FieldValue(
                                        value=value,
                                        confidence=0.5,
                                        page=p,
                                        source="vlm",
                                    )
                    except Exception as exc:
                        processing_errors.append(
                            f"VLM unavailable for section {page_ids}: {exc}"
                        )
            if page_tables:
                from fextract.tables.stitch import stitch_tables

                stitched = stitch_tables(
                    [
                        table
                        for page_id in page_ids
                        for table in page_tables.get(page_id, [])
                    ]
                )
                if (
                    group["doc_type"] != "bank_statement"
                    and len(stitched) > 1
                    and stitched[0]
                ):
                    headers = [str(header).strip() for header in stitched[0]]
                    extracted_rows = [
                        dict(zip(headers, row))
                        for row in stitched[1:]
                        if len(row) == len(headers)
                    ]
                    if extracted_rows:
                        tables.setdefault(
                            (
                                "line_items"
                                if group["doc_type"] == "commercial_invoice"
                                else "tables"
                            ),
                            extracted_rows,
                        )
            for item in fields.values():
                source_page = item.page if item.page in paths else page_ids[0]
                item.source_layer = paths.get(source_page)
            if group["doc_type"] == "unknown":
                fields = {}
                reason = (
                    "unreadable_page" if not text.strip() else "unknown_document_type"
                )
                needs_review.append(f"section_{len(sections) + 1}.{reason}")
            validations = validate_section(group["doc_type"], fields, tables)
            source_score = sum(source_scores.get(page, 1.0) for page in page_ids) / max(
                len(page_ids), 1
            )
            needs_review.extend(
                f"section_{len(sections) + 1}.{name}"
                for name in flag_fields(fields, validations, threshold, source_score)
            )
            sections.append(
                SectionResult(
                    doc_type=group["doc_type"],
                    doc_type_confidence=group["doc_type_confidence"],
                    pages=page_ids,
                    fields=fields,
                    tables=tables,
                    validation=validations,
                )
            )
        if any(
            section.doc_type
            in {"balance_sheet", "profit_and_loss", "cash_flow_statement"}
            for section in sections
        ):
            cross_section_validation = validate_cross_sections(
                sections,
                {page: value for page, value in enumerate(pages, start=1)},
                {page: words_for_page(page) for page in paths},
            )
        else:
            cross_section_validation = []
        return DocumentResult(
            source_file=path.name,
            page_count=page_count,
            extraction_paths=paths,
            source_quality=source_quality,
            sections=sections,
            cross_section_validation=cross_section_validation,
            needs_review=needs_review,
            errors=processing_errors,
            timings_ms={"total": (perf_counter() - started) * 1000},
        )
    except Exception as exc:
        return DocumentResult(
            source_file=path.name,
            page_count=0,
            extraction_paths={},
            sections=[],
            needs_review=[],
            errors=[f"{type(exc).__name__}: {exc}"],
            timings_ms={"total": (perf_counter() - started) * 1000},
        )


def _ocr_words_to_lines(words):
    """Reconstruct OCR text in reading order, preserving horizontal rows."""
    ordered = sorted(words, key=lambda word: (word.bbox[1], word.bbox[0]))
    rows = []
    for word in ordered:
        top, bottom = word.bbox[1], word.bbox[3]
        center = (top + bottom) / 2
        height = max(1.0, bottom - top)
        row = next(
            (
                candidate
                for candidate in reversed(rows)
                if abs(candidate["center"] - center)
                <= max(4.0, min(candidate["height"], height) * 0.6)
            ),
            None,
        )
        if row is None:
            rows.append({"center": center, "height": height, "words": [word]})
        else:
            row["words"].append(word)
            row["center"] = sum(
                (item.bbox[1] + item.bbox[3]) / 2 for item in row["words"]
            ) / len(row["words"])
            row["height"] = max(row["height"], height)
    return "\n".join(
        " ".join(
            word.text for word in sorted(row["words"], key=lambda item: item.bbox[0])
        )
        for row in sorted(rows, key=lambda item: item["center"])
    )
