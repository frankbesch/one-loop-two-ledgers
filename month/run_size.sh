#!/usr/bin/env bash
# Packet-size test driver (publishing one-loop-two-ledgers/18-packet-size-preregistration.md §2, §4).
# Rounds x sizes d3 d6 d12 d24, months 3-6, arm B worksheet-calc on claude-sonnet-5-5 (subscription only: no key,
# no metered spend). One output folder per run-set, reserved with mkdir (never reused). Scores each run-set as it
# finishes. A voided run-set (VOID.txt) is logged and kept, not scored, and the driver goes on; a failed-closed
# month is logged INCOMPLETE. Repeats are run by hand in new folders (§4); this script never repeats or deletes.
# arm_b.py exit 6 is a void the runner wrote; any other non-zero exit (crash, refusal) makes the driver write
# VOID.txt itself (rc and the last 20 log lines) and go on to the next run-set.
# Rounds are capped at 8: rounds 1-5 plus replacement rounds 6-8 (pre-registration); --rounds or --start-round
# above 8 is refused.
#   bash run_size.sh                                 live, rounds 1-5, all four sizes
#   bash run_size.sh --rounds 1                      live, round 1 only
#   bash run_size.sh --start-round 3 --rounds 5      live, rounds 3-5 (--rounds is the last round number)
#   bash run_size.sh --sizes "d6 d24"                live, only these sizes, in each round's table order
#   bash run_size.sh --smoke                         oracle backend, round 1, to results/_scratch/ (harness check, no calls)
#   SIZE_SMOKE_CRASH=d6 bash run_size.sh --smoke ... smoke only: arm_b.py gets a packet file that does not exist for
#                                                    that size, so it crashes; tests the driver's crash void. Refused
#                                                    (exit 2) without --smoke, so it cannot touch a live run.
# Exit codes: 2 bad arguments, 3 preflight, 4 folder exists, 5 meta.json unreadable after rc 0, 7 scoring failed.
#
# Size order per round: a fixed table, generated once (2026-10-14) with
#   python3 -c "import random; r=random.Random(1014); b=['d3','d6','d12','d24']
#   for i in range(1,9): x=list(b); r.shuffle(x); print(f'ORDER_r{i}=('+' '.join(x)+')')"
# Each round shuffles a fresh copy of [d3 d6 d12 d24] with the one seeded generator. There is no round 9.
ORDER_r1=(d12 d6 d24 d3)
ORDER_r2=(d24 d12 d6 d3)
ORDER_r3=(d3 d12 d24 d6)
ORDER_r4=(d3 d6 d24 d12)
ORDER_r5=(d6 d12 d3 d24)
ORDER_r6=(d24 d3 d12 d6)
ORDER_r7=(d24 d3 d12 d6)
ORDER_r8=(d3 d6 d24 d12)
set -u
cd "$(dirname "$0")" || exit 2
ROUNDS=""; START=1; SIZES="d3 d6 d12 d24"; SMOKE=0
BACKEND=claude; MODE=live; MODEL=claude-sonnet-5-5; RESULTS=results; TAG=SIZE
posint(){ case "$1" in ''|*[!0-9]*|0*) return 1;; esac; return 0; }
need(){ [ "$2" -ge 2 ] || { echo "REFUSED: $1 needs a value" >&2; exit 2; }; }
while [ $# -gt 0 ]; do case "$1" in
  --rounds) need "$1" $#; ROUNDS="$2"; shift 2;;
  --start-round) need "$1" $#; START="$2"; shift 2;;
  --sizes) need "$1" $#; SIZES="$2"; shift 2;;
  --smoke) SMOKE=1; shift;;
  *) echo "REFUSED: unknown arg $1" >&2; exit 2;; esac; done
if [ "$SMOKE" = 1 ]; then BACKEND=oracle; MODE=dry-run; RESULTS=results/_scratch; TAG=SIZE-smoke; fi
[ -n "$ROUNDS" ] || { [ "$SMOKE" = 1 ] && ROUNDS=1 || ROUNDS=5; }
posint "$ROUNDS" || { echo "REFUSED: --rounds must be a positive integer, got '$ROUNDS'" >&2; exit 2; }
posint "$START" || { echo "REFUSED: --start-round must be a positive integer, got '$START'" >&2; exit 2; }
[ "$ROUNDS" -le 8 ] || { echo "REFUSED: --rounds $ROUNDS is above 8 (rounds 1-5 plus replacement rounds 6-8)" >&2; exit 2; }
[ "$START" -le 8 ] || { echo "REFUSED: --start-round $START is above 8 (rounds 1-5 plus replacement rounds 6-8)" >&2; exit 2; }
[ "$START" -le "$ROUNDS" ] || { echo "REFUSED: --start-round $START is after the last round --rounds $ROUNDS" >&2; exit 2; }
SEL=" "
for s in $SIZES; do
  case "$s" in d3|d6|d12|d24) ;; *) echo "REFUSED: --sizes takes d3 d6 d12 d24, got '$s'" >&2; exit 2;; esac
  case "$SEL" in *" $s "*) ;; *) SEL="$SEL$s ";; esac
done
[ "$SEL" != " " ] || { echo "REFUSED: --sizes is empty" >&2; exit 2; }
CRASH="${SIZE_SMOKE_CRASH:-}"
if [ -n "$CRASH" ]; then
  [ "$SMOKE" = 1 ] || { echo "REFUSED: SIZE_SMOKE_CRASH is a smoke-only test hook; unset it for a live run" >&2; exit 2; }
  case "$CRASH" in d3|d6|d12|d24) ;; *) echo "REFUSED: SIZE_SMOKE_CRASH takes d3 d6 d12 d24, got '$CRASH'" >&2; exit 2;; esac
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ); mkdir -p "$RESULTS"; LOG="$RESULTS/$TAG-driver-$STAMP.log"
log(){ echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
tally(){
  python3 - "$RESULTS" "$TAG" <<'PY' | tee -a "$LOG"
import json, re, sys
from pathlib import Path
res, tag = Path(sys.argv[1]), sys.argv[2]
t = {s: {'complete': [], 'incomplete': [], 'void': []} for s in ('d3', 'd6', 'd12', 'd24')}
voided, failed_closed = [], []
for d in sorted(res.glob(tag + '-*')):
    m = re.fullmatch(re.escape(tag) + r'-(d\d+)-r(\d+)', d.name)
    if not d.is_dir() or not m or m.group(1) not in t:
        continue
    try:
        fc = json.loads((d / 'meta.json').read_text()).get('months_failed_closed') or []
    except (OSError, ValueError):
        fc = ['no meta.json']
    if fc != ['no meta.json'] and fc:
        failed_closed.append(f'{d} {fc}')
    if (d / 'VOID.txt').exists():
        k = 'void'; voided.append(str(d))
    else:
        k = 'complete' if not fc and (d / 'score.json').exists() else 'incomplete'
    t[m.group(1)][k].append('r' + m.group(2))
print(f'tally of {res}/{tag}-*: complete / incomplete / void run-sets per size')
for s, v in t.items():
    print(f"  {s:>3}: {len(v['complete'])} / {len(v['incomplete'])} / {len(v['void'])}"
          + ''.join(f'  {k}={",".join(x)}' for k, x in v.items() if x and k != 'complete'))
print(f'folders with VOID.txt ({len(voided)}):' + ''.join(f'\n  {x}' for x in voided))
print(f'folders with months_failed_closed ({len(failed_closed)}):' + ''.join(f'\n  {x}' for x in failed_closed))
PY
}
PHASE=preflight; TALLY=0
trap 'rc=$?; [ "$TALLY" = 1 ] && tally; log "EXIT rc=$rc (phase=$PHASE)"' EXIT
log "preflight: driver $STAMP backend=$BACKEND mode=$MODE rounds=$START-$ROUNDS sizes=$SEL${CRASH:+ SMOKE CRASH HOOK size=$CRASH}"
[ -f packets/packets.json ] || { log "REFUSED: packets/packets.json missing"; exit 3; }
if [ "$MODE" = live ]; then
  [ -f frozen/FREEZE-SIZE.json ] || { log "REFUSED: frozen/FREEZE-SIZE.json missing (freeze first)"; exit 3; }
  command -v claude >/dev/null || { log "REFUSED: claude CLI missing"; exit 3; }
  log "claude $(claude --version 2>&1 | head -1)"
fi
TALLY=1
for r in $(seq "$START" "$ROUNDS"); do
  eval "ORD=(\"\${ORDER_r$r[@]}\")"
  for s in "${ORD[@]}"; do
    case "$SEL" in *" $s "*) ;; *) continue;; esac
    OUT="$RESULTS/$TAG-$s-r$r"; PHASE="reserve $s r$r"
    mkdir "$OUT" 2>>"$LOG" || { log "REFUSED: $OUT exists or cannot be made (one folder per run-set, never reused)"; exit 4; }
    PHASE="run $s r$r"; log "start $OUT (round $r order ORDER_r$r: ${ORD[*]})"
    PK=packets/packets.json
    [ "$SMOKE" = 1 ] && [ "$CRASH" = "$s" ] && { PK=packets/_smoke-crash-no-such-file.json; log "SMOKE CRASH HOOK: --packet $PK for $OUT"; }
    ARGS=(--months 3 4 5 6 --backend "$BACKEND" --mode "$MODE" --prompt-variant worksheet-calc --packet "$PK" --size "$s" --out "$OUT")
    [ "$MODE" = live ] && ARGS+=(--model "$MODEL" --frozen frozen/FREEZE-SIZE.json)
    python3 arm_b.py "${ARGS[@]}" >>"$LOG" 2>&1; rc=$?
    log "finished $OUT rc=$rc"
    if [ $rc -ne 0 ] && { [ $rc -ne 6 ] || [ ! -f "$OUT/VOID.txt" ]; }; then
      { echo "driver: arm_b.py exit rc=$rc (crash or refusal)"; echo; echo "last 20 log lines:"; tail -n 20 "$LOG"; } >>"$OUT/VOID.txt"
    fi
    if [ -f "$OUT/VOID.txt" ]; then log "VOID $OUT rc=$rc: $(head -1 "$OUT/VOID.txt")"; continue; fi
    FC=$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("months_failed_closed") or []))' "$OUT/meta.json" 2>>"$LOG") \
      || { log "STOP: cannot read $OUT/meta.json"; exit 5; }
    [ "$FC" = "[]" ] || log "INCOMPLETE $OUT months_failed_closed=$FC"
    PHASE="score $s r$r"
    python3 score_month.py "$OUT" >>"$LOG" 2>&1 || { log "STOP: score_month.py failed for $OUT"; exit 7; }
    [ -f "$OUT/score.json" ] || { log "STOP: $OUT/score.json missing after scoring"; exit 7; }
  done
done
PHASE=done; log "all run-sets finished"
