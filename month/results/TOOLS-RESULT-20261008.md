# One Loop step 6: arm B with a calculator tool (2026-10-08)

Pre-registered before the scored runs in publishing `one-loop-two-ledgers/07-b-tools-plan.md` (0e31d1d), with the re-freeze in private source f7fdcbf.
- Three runs (c1-c3) on months 3-6, `claude-sonnet-5-5`, with the worksheet prompt plus the `calculate` tool.
- No call errors, no void. Every month used the tool. Every run is reported.
- Summary data: `TOOLS-summary.json`.

## Results (months 3-6; the key holds 148 lines and 96 money errors)

| Single-agent design | Silent per run | Held per run | False holds | Money caught | Tool calls per month | List-price est. per month |
|---|---|---|---|---|---|---|
| Worksheet + calculator (c1-c3) | **0, 0, 1** | 148, 148, 148 | 0, 0, 1 | 96, 96, 95 | 5-26 | $0.56-0.78 |
| Worksheet (w1-w3) | 0, 3, 0 | 148, 145, 148 | 0, 0, 0 | 96, 95, 96 | none | $0.50-0.72 |
| v1 prompt (r1-r3) | 1, 1, 2 | 147, 147, 147 | 0, 0, 1 | 95, 95, 94 | none | $0.33-0.53 |
| **D, this architecture (r1-r3)** | **0, 0, 0** | 154, 154, 152 | 6, 6, 4 | 96, 96, 96 | n/a | **Jev $0.007, measured** |

## Claims (pre-registered)

| # | Claim | Result |
|---|---|---|
| H9 | A tool does not make the single agent reliable on every run | **PASS**: c3 let 1 line through unseen |
| H10 | The tool does not fix reading errors | **PASS**: c3's miss was a misread, not arithmetic (below) |
| H11 | D's cost per month stays below the tool agent's | **PASS**: $0.007 measured, against $0.56-0.78 at list price, an estimate |

## The miss, traced from the run's own logs

- **c3, m3_jib_12 line 1:** the same line that v1 missed in 3 of 3 runs and the worksheet missed in 1 of 3.
  - The page prints 0.1125; the decimal in force is 0.0875.
  - c3's worksheet row reads `LX/874/P|0.0875|0.0875`: the agent wrote the expected value into the "printed" column.
  - c3's calculator log for month 3 holds 15 calls, and none compares 0.1125 with 0.0875.
- **c1 caught the same line.** Its log holds `0.1125-0.0875 = 0.0250`.
- **The calculator computes exactly on whatever the agent hands it.** It cannot check a number the agent misread.
- **The agent used the tool selectively:** 5-26 calls a month for 210 lines, although the prompt says to use it "for every number you compare or compute."

## Findings across all single-agent designs (9 runs) and D (3 runs)

1. **Every single-agent design let something through unseen in at least one run.** That covers 5 of 9 runs; D had 0 of 3.
2. **The same line is behind it.** A wrong owner decimal that equals another property's real decimal in force got through in 5 of 9 single-agent runs: v1 3/3, worksheet 1/3, worksheet plus calculator 1/3. D caught it 3/3.
3. **The mechanism is a reading error, not an arithmetic one.** In the logged failures the agent recorded the value it expected instead of the value printed. A worksheet and a calculator each lowered the miss rate, but neither removed it, because both depend on what the agent believes it read.
4. **Prompt and tools trade cost for reliability, and the gap does not close.** The best single agent (worksheet plus calculator) caught everything in 2 of 3 runs, at about 80-115 times D's monthly cost at list price. It held fewer lines than D: 148 against 152-154, which is 4-6 fewer reviews over four months.
5. **Actionable rules:**
   - Let code read printed values and look them up. A model's own worksheet is not evidence of what is on the page.
   - Judge an agent by its worst run; a review team cannot tell which run was the bad one.

## Limits

- The two prompts and the tool were designed by us, after seeing v1's miss. Other designs are untested: code execution, per-document calls, or a second model checking the first.
- Three runs per design. "1 bad run in 3" is an observation, not a rate.
- One synthetic corpus. The blind spot is one constructed case (a share transfer whose new decimal matches another property's). Real billing data will hold others, not necessarily this one.
