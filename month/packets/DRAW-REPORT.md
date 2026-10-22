# Packet draw report

The script read only `../synth-month/truth_m.json`, using `month`, `doc_id`, and `money_error` from `lines`.

It counted truth lines and non-`none` errors for each document.
It used one `random.Random(1014)` stream, processing months 3, 4, 5, and 6 in order.
Within each month, it sampled d12, then d6 within d12, then d3 within d6.
Every sampling population used sorted document IDs.
Each attempt sampled without replacement; rejected attempts consumed the same random stream.
Attempts include the accepted draw.

Error ranges were 10–14 for d12, 5–7 for d6, and 2–4 for d3.
Invoice ranges were 2–4 for d12, 1–2 for d6, and 0–1 for d3.
Each d24 contains all 24 sorted document IDs; no random draw was needed.

Validation passed for counts, sizes, nesting, sorting, error ranges, invoice ranges, and complete d24 coverage.
Packet selections and counts are deterministic for unchanged input; `drawn_at` records the current UTC execution time.

| Packet | Month | Docs | Lines | Errors | Invoices | Attempts |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| d3 | m3 | 3 | 26 | 2 | 1 | 1 |
| d3 | m4 | 3 | 26 | 4 | 1 | 1 |
| d3 | m5 | 3 | 27 | 4 | 0 | 2 |
| d3 | m6 | 3 | 26 | 2 | 1 | 2 |
| d6 | m3 | 6 | 52 | 6 | 2 | 1 |
| d6 | m4 | 6 | 53 | 7 | 1 | 1 |
| d6 | m5 | 6 | 53 | 5 | 1 | 2 |
| d6 | m6 | 6 | 52 | 6 | 2 | 3 |
| d12 | m3 | 12 | 104 | 14 | 4 | 1 |
| d12 | m4 | 12 | 104 | 12 | 4 | 1 |
| d12 | m5 | 12 | 105 | 10 | 3 | 1 |
| d12 | m6 | 12 | 104 | 13 | 4 | 2 |
| d24 | m3 | 24 | 210 | 24 | 6 | — |
| d24 | m4 | 24 | 210 | 24 | 6 | — |
| d24 | m5 | 24 | 210 | 24 | 6 | — |
| d24 | m6 | 24 | 210 | 24 | 6 | — |

Exact command run from the `month` directory:

```sh
python3 packets/draw_packets.py
```
