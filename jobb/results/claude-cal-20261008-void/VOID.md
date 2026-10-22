# VOID: Claude calibration rerun started 15:40 UTC, 2026-10-08

A prompt bug sent the literal string `{text}` instead of the unit text: an f-string prefix was dropped when the Q7 evidence line was edited. With no text to read, Claude correctly answered `needs_review` with "no evidence in text" on 194 of 210 Q2 calls. The run measures nothing about the model and is not a result. Score and meta are kept only as the record.
Fix: private source `854e8ec`. `claude_prompt` now asserts that the unit text reaches the prompt, so a dry run fails on this class of bug. The valid rerun is `../claude-cal-20261008-v2/`.
