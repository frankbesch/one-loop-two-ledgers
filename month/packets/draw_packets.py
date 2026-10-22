#!/usr/bin/env python3
"""Draw reproducible nested packets using only the permitted truth fields."""

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path


SEED = 1014
ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT.parent / "synth-month" / "truth_m.json"
OUTPUT = ROOT / "packets"
COMMAND = "python3 packets/draw_packets.py"
RULE = (
    "For months 3–6, draw nested d12, d6, and d3 packets by seeded rejection "
    "sampling with error tolerances 2, 1, and 1 and invoice counts within 1 "
    "of one quarter of packet size; d24 contains every document."
)


def summarize(selected, documents):
    return {
        "docs": len(selected),
        "lines": sum(documents[d]["lines"] for d in selected),
        "errors": sum(documents[d]["errors"] for d in selected),
        "invoices": sum("_inv_" in d for d in selected),
    }


def acceptable(counts, size):
    tolerance = 2 if size == 12 else 1
    return (
        abs(counts["errors"] - size) <= tolerance
        and abs(counts["invoices"] - size / 4) <= 1
    )


def main():
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))["lines"]
    months = {month: {} for month in (3, 4, 5, 6)}
    for row in rows:
        month = row["month"]
        if month not in months:
            continue
        doc_id = row["doc_id"]
        if not re.fullmatch(rf"m{month}_(inv|jib)_\d{{2}}", doc_id):
            raise ValueError(f"Unexpected document ID: {doc_id}")
        document = months[month].setdefault(doc_id, {"lines": 0, "errors": 0})
        document["lines"] += 1
        document["errors"] += row["money_error"] != "none"

    rng = random.Random(1014)
    sizes = {f"d{k}": {} for k in (3, 6, 12, 24)}
    counts = {key: {} for key in sizes}
    attempts = {}
    for month, documents in months.items():
        key = f"m{month}"
        population = sorted(documents)
        if len(population) != 24 or sum("_inv_" in d for d in population) != 6:
            raise ValueError(f"{key} must contain 6 invoices and 18 JIB statements")
        sizes["d24"][key] = population
        counts["d24"][key] = summarize(population, documents)
        for size in (12, 6, 3):
            attempt = 0
            while True:
                attempt += 1
                selected = sorted(rng.sample(population, size))
                summary = summarize(selected, documents)
                if acceptable(summary, size):
                    break
            label = f"d{size}"
            sizes[label][key] = selected
            counts[label][key] = summary
            attempts[(label, key)] = attempt
            population = selected

    # Validate all constraints before writing either output.
    for month, documents in months.items():
        key = f"m{month}"
        previous = set()
        for size in (3, 6, 12, 24):
            label = f"d{size}"
            selected = sizes[label][key]
            assert selected == sorted(set(selected)) and len(selected) == size
            assert previous <= set(selected)
            assert counts[label][key] == summarize(selected, documents)
            if size != 24:
                assert acceptable(counts[label][key], size)
            else:
                assert selected == sorted(documents)
            previous = set(selected)

    payload = {
        "seed": SEED,
        "drawn_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rule": RULE,
        "sizes": sizes,
        "counts": counts,
    }
    table = [
        "| Packet | Month | Docs | Lines | Errors | Invoices | Attempts |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in sizes:
        for month in months:
            key = f"m{month}"
            c = counts[label][key]
            attempt = attempts.get((label, key), "—")
            table.append(
                f"| {label} | {key} | {c['docs']} | {c['lines']} | "
                f"{c['errors']} | {c['invoices']} | {attempt} |"
            )
    table_text = "\n".join(table)
    report = (
        "# Packet draw report\n\n"
        "The script read only `../synth-month/truth_m.json`, using `month`, `doc_id`, and `money_error` from `lines`.\n\n"
        "It counted truth lines and non-`none` errors for each document.\n"
        "It used one `random.Random(1014)` stream, processing months 3, 4, 5, and 6 in order.\n"
        "Within each month, it sampled d12, then d6 within d12, then d3 within d6.\n"
        "Every sampling population used sorted document IDs.\n"
        "Each attempt sampled without replacement; rejected attempts consumed the same random stream.\n"
        "Attempts include the accepted draw.\n\n"
        "Error ranges were 10–14 for d12, 5–7 for d6, and 2–4 for d3.\n"
        "Invoice ranges were 2–4 for d12, 1–2 for d6, and 0–1 for d3.\n"
        "Each d24 contains all 24 sorted document IDs; no random draw was needed.\n\n"
        "Validation passed for counts, sizes, nesting, sorting, error ranges, invoice ranges, and complete d24 coverage.\n"
        "Packet selections and counts are deterministic for unchanged input; `drawn_at` records the current UTC execution time.\n\n"
        + table_text
        + "\n\nExact command run from the `month` directory:\n\n```sh\n"
        + COMMAND
        + "\n```\n"
    )
    (OUTPUT / "packets.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "DRAW-REPORT.md").write_text(report, encoding="utf-8")
    print(table_text)


if __name__ == "__main__":
    main()
