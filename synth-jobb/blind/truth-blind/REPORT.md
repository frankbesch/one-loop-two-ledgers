# Blind re-key report

Keyed 48 documents across 64 page images: 420 bill lines and 96 remarks.

Nulls: 96 `claim_text` values, all for lines with no approval claim. No other nulls.

Unsure lines: none. No `UNSURE` values.

Labels were keyed by eye from page images. Only `afe_register.json` supplied register lookup information.
Printed words, numbers, and punctuation were preserved; wrapped text was joined with spaces.
Remark IDs follow reading order across each document's pages.

Validation checked document coverage, line counts, page existence, remark links, and label consistency.
