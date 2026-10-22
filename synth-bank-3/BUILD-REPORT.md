# Step 7d stress banking set: build report (2026-10-09)

**Verdict: BUILT, VALID, AND FROZEN, with one logged designer rebuild and one reader fix before the freeze.** No model answered any question on this set before the freeze.
- 48 certificates (4 quarters × 12 new borrowers), 395 units.
- 4 dependent cap cases per quarter. The scored quarters' key holds 46 units.
- **Pre-registration:** publishing `one-loop-two-ledgers/15-stress-set-preregistration.md` (`76b1ef6`).
- **Amendment 1:** `72589ef`. The builder is Claude Opus (`claude-opus-5-5`), because Codex hit its usage limit; the Codex designer attempt wrote no spec.
- **Brief:** the data brief (unpublished).

## Sessions (Claude Opus via the CLI on the subscription; fresh folder outside every repository; `--setting-sources project`; no web tools; containment scanned)

| Stage | Result | Containment |
|---|---|---|
| Designer, Codex | Hit the usage limit; no spec written | clean |
| Designer, Opus run 1 | Stress gate passed, but the spec check found **3 differences**, all on one unit. q2_b09 prints the signer title "VP Finance" against "Vice President of Finance". The frozen title rule expands "VP" but keeps "of", so it would not match. The prompt was tightened (abbreviations expand word for word) and the designer re-run (private source `efb7ac7`). | clean |
| Designer, Opus run 2 | 395 units. Independent spec check **0 differences**. Stress gate (`bank/check_stress_q.py`) **0 failures**, 4 dependent cap cases per quarter. Every anchor's wording mixes achieved and expected savings. No step 7 or 7c entity name recurs. | clean |
| Generator | 48 sources, 395 truth units, no deviations. G1-G4 and G7 pass. | It copied its own folder into its CLI scratchpad to test that its gate fails on bad data. Nothing was read from outside its folder. |
| Render (brain) | 48 PDFs, 79 page images; G1-G7 all **PASS** | n/a |
| Reader check | The frozen reader failed on 41 of 48: Opus right-aligns amounts, starting left of the "Amount" header. **Reader fix** (`90d8ddd`, from printed values only): to the right of the description, money and date tokens go to Amount and Action. After the fix: 48 of 48 exact, and identical output on every step 7 and 7c certificate. | n/a |
| Blind re-key, one session per quarter | Error class, breach, disposition, owner, and realized agree with the key on **395 of 395** units, including every anchor's realized label | q2 ran `cd ../page-images` from a subfolder of its own folder; nothing outside |
| Adjudicator | 24 differences, all one keyer's format for the printed threshold (text, such as "Minimum 2.50x", against the number). The key was right each time. **0 unresolved.** | It used its own CLI scratchpad; nothing outside |
| Freeze | `frozen-q.json`: 55 files; the synth-bank-3 copy hashes clean | n/a |
