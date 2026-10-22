# Blind re-key report

Keyed 24 documents, 216 bill lines, and 44 remarks from all 48 page images by eye.

The JSON files contain 48 null values, all in `claim_text` for lines with no claim. No other fields are null. No values are `UNSURE`; no line IDs require uncertainty review.

Remark IDs restart at 1 on each page, following the stated definition. Array order preserves page order and printed remark order. Printed words and punctuation are preserved; visual line wraps become spaces.

Only the supplied definitions, page images, and AFE register informed the labels. The register served only as a lookup. No source content was corrected.

Validation passed for document coverage, line coverage, field sets, label values, remark links, and register lookups.
