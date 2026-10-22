"""Step 6 learning loop: the month-close challenger and the promotion rule (Frank, 2026-10-08).

Labels the system has: the person's decision on every held line (the key plays the person) and the audit
sample of posted lines. A challenger is a floor set found by coordinate descent on the arm's own logged
answers for every month so far (replayed, no new calls). It is promoted only when, on every past month, its
replay shows 0 new silent errors on labelled lines and no more held lines, with fewer held lines in total.
Each promotion is logged as a signed proposal: Frank's approval of the rule covers it.
"""
import json
from pathlib import Path

import mcode as M
import munits as MU

GRID = [round(0.40 + 0.05 * i, 2) for i in range(12)]
QS = ['Q2', 'Q5', 'Q7', 'Q9']


def replay_months(RM, arm_args, truth, ref, formats, period, months, units, labels, floors, run_dir, tmp):
    """Replay the run's own answers at `floors`. -> {month: (silent_on_labelled, held)}."""
    import copy
    rargs = copy.copy(arm_args)
    rargs.backend, rargs.mode = 'replay', 'dry-run'      # the loop never calls a model: logged answers only
    Path(tmp).mkdir(parents=True, exist_ok=True)
    reg = M.Register(ref['afe_register'], formats)
    arm = RM.Arm(rargs, truth, reg, ref['properties'], tmp)
    arm.floors = floors
    arm.replay = RM.Replay({'*': run_dir})
    out, state = {}, None
    for m in months:
        money = M.Money(ref, reg, state)
        s = h = 0
        for u in units[m]:
            arm.ord = {}
            r = arm.line(m, u, money, period[m])
            lab = labels.get((u['doc_id'], u['line_no']))
            s += r['disposition'] == 'post' and lab == 'hold'
            h += r['disposition'] == 'hold'
        state = money.state()
        out[m] = (s, h)
    arm.log.close()
    return out


def challenger(RM, arm_args, truth, ref, formats, period, months, run_dir, labels, running, tmp):
    """-> (proposal dict, promoted bool)."""
    units = {m: sorted(MU.load_month(Path(arm_args.corpus), m, formats)[0], key=lambda u: (u['doc_id'], u['line_no']))
             for m in months}
    def ev(fl):
        return replay_months(RM, arm_args, truth, ref, formats, period, months, units, labels, fl, run_dir, tmp)
    base = ev(running)
    floors = dict(running)
    for _ in range(2):
        for q in QS:
            best = None
            for f in GRID:
                trial = dict(floors, **{q: f})
                r = ev(trial)
                key = (sum(x[0] for x in r.values()), sum(x[1] for x in r.values()), -f)
                if best is None or key < best[0]:
                    best = (key, f, r)
            floors[q] = best[1]
    chal = ev(floors)
    ok = (all(chal[m][0] <= base[m][0] for m in months) and all(chal[m][1] <= base[m][1] for m in months)
          and sum(c[1] for c in chal.values()) < sum(b[1] for b in base.values()))
    prop = dict(months=months, running=running, challenger=floors, running_replay={str(m): base[m] for m in months},
                challenger_replay={str(m): chal[m] for m in months}, promoted=ok,
                rule='0 new silent on labelled lines and no more held on every past month; fewer held in total',
                signed='Frank, 2026-10-08: promotion rule approved (auto when strictly better)' if ok else None)
    return prop, ok
