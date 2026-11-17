# Sample document results

Results of running `fextract` on the six provided sample documents (88 pages). The documents are not committed because they contain real financial and personal data; names, tax numbers and addresses are omitted here. Reproduced from a clean install (Python 3.12, Tesseract 5.3) with `fextract run --input data/samples --output results`.

All six completed with zero errors. "Flagged" is the number of fields listed in `needs_review` at the default 0.7 threshold.

| Document | Pages | Text source | Sections found | Flagged |
|---|---:|---|---|---:|
| Document1 | 3 | digital | balance sheet (p1), notes_other (p2-3) | 0 |
| Document2 | 8 | digital | commercial invoice (p1-8) | 0 |
| Document3 | 12 | embedded layer on 11 pages, OCR on 1 | audit report (p1-5), balance sheet (p6), P&L (p7), notes (p8-12) | 13 |
| Document4 | 47 | digital | notes (p1), audit report (p2), balance sheet (p3-4), P&L (p5-6), notes (p7), cash flow (p8-9), notes (p10-47) | 24 |
| Document5 | 2 | digital | cash flow statement (p1-2) | 0 |
| Document6 | 16 | digital | bank statement (p1-16) | 4 |

## Key results and validation

- **Document1:** total assets and total liabilities both 7,220,444 (check passed); as-on date, assessment year and financial year extracted.
- **Document2:** invoice number, date, currency, incoterm, customer number, total sales value 27,743.11, freight 0.00 and net weight 25.021 kg. 65 line items; line sum equals the total and quantity x unit price holds for every line.
- **Document3:** scanned audit pack with a noisy embedded text layer. Fresh OCR was compared against the embedded layer for every page; the embedded layer was kept on 11 pages because the scan has obscured amounts that only the embedded layer still contains. Balance sheet totals 66,980 on both sides; revenue 81,250, expenses 129,770, profit before tax and profit (48,520); report date 2022-09-06. Other income, exceptional items and tax are nil and are marked `derived`. All three cross-section checks (profit equals reserves, EPS, cash note) pass.
- **Document4:** balance sheet 17,149 on both sides; P&L for both years (revenue 35,218 and 34,487; profit 5,237 and 4,490); cash flow for both years (operating 5,916, investing (1,264), financing (4,651), net change 1, cash 572 to 573); EPS cross-check passes. All statement checks pass.
- **Document5:** both years extracted in lakhs; operating, investing and financing activities sum to the net change (1,526.31 decrease); cash moves from 1,547.52 to 21.21.
- **Document6:** 130 transactions, dates in order, running balance check passes. The first page of the original statement is not included, so account holder and period are `null` with `not_present`. Opening balance 177,347.06 and closing balance 334,994.27 are `derived` from the first and last transaction rows.

## Verification

64 headline fields across the six documents (identifiers, dates, totals, statement line items and balances) were compared by hand against the source PDFs and are stored in `data/ground_truth/`. All 64 matched the extracted values. The row counts of 65 invoice line items and 130 bank transactions were confirmed against the source text.

This is development-set accuracy: the extraction rules were written while looking at these documents. The synthetic benchmark in the README is the measure for unseen layouts.

## Known gaps

- Document3 and Document4 each keep a long notes section as `notes_other`; it is not split by note number.
- Document1's capital schedule is `notes_other`.
- Document4's page 1 (a short continuation page) is labelled `notes_other` with low section confidence (0.35).
- Review flags are cautious: 13 of the 64 verified correct fields were still flagged.
