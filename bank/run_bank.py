#!/usr/bin/env python3
"""Step 7 arm D on the banking mirror: the loop, quarter by quarter (10-banking-mirror-plan.md §4).

  run_bank.py --quarters 1 2 --backend oracle                                         harness proof
  run_bank.py --quarters 1 2 --backend claude --mode live --model claude-sonnet-5-5     calibration (subscription)
  run_bank.py --quarters 1 2 3 4 --backend claude --mode live --model claude-sonnet-5-5 --loop --frozen bank/frozen/FREEZE-BANK.json --rule frozen
  run_bank.py ... --loop --frozen bank/frozen/FREEZE-BANK-2.json --rule invariant                    the cap-fix re-run

Per quarter: code reads each certificate (bunits.py); the model answers QC, QR, QX per addback (bquestions.py);
code applies the agreement (bcode.py): addback tests, the cure test against the bank's cure records, ratios,
breach, delivery, signer, and the owner rule. A "needs review" answer holds its addback. Under --rule invariant
any unit that would hold under some resolution of a doubted answer is held too; the frozen step 7 rule guarded
covenants only, with a stand-in that could not fire. Close: a 5% random audit of posted units against the key; the key
plays the person on every held unit; the learning step (step 6's promotion rule) may lower floors after each quarter.
Outputs: runs/bank/<arm>/: calls.jsonl, q<k>/outcomes.json, q<k>/close.json, promotions.json, meta.json.
"""
import argparse, datetime, hashlib, json, random, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(DEMO / 'jobb')); sys.path.insert(0, str(DEMO / 'typed'))
import bcode as B  # noqa: E402
import bquestions as BQ  # noqa: E402
import bunits as BU  # noqa: E402
import jev_backend as jev  # noqa: E402
from codelayer import NEEDS_REVIEW  # noqa: E402

DEFAULT_FLOOR = 0.60
AUDIT_SHARE = 0.05
GRID = [round(0.40 + 0.05 * i, 2) for i in range(12)]
QIDS = ('QC', 'QR', 'QX')


def load_ref(corpus, quarter):
    ref = Path(corpus) / 'reference'
    ags = json.loads((ref / 'agreements.json').read_text())
    cats = json.loads((ref / 'categories.json').read_text())
    prior = json.loads((ref / f'prior_cures_q{quarter}.json').read_text())
    return ags, cats, prior


class Oracle:
    """Perfect answers from the key (harness proof only)."""

    def __init__(self, truth):
        self.u = {(u['cert_id'], u['unit_id']): u for u in truth['units']}

    def ask(self, qid, cert_id, addback_no, text, cats):
        u = self.u[(cert_id, f'A{addback_no}')]
        key = {'QC': u['category_true'], 'QR': u.get('realized'), 'QX': u.get('certified')}[qid]
        opts = list(BQ.options(qid, cats)) + [NEEDS_REVIEW]
        rest = 0.1 / (len(opts) - 1)
        ev = text.split('\n', 1)[-1] if key not in ('no',) else 'no evidence in text'
        if qid == 'QX' and key == 'yes':
            ev = text.split('paragraph: ', 1)[-1]
        return {'answer': key, 'probabilities': {o: (0.9 if o == key else rest) for o in opts}, 'evidence': ev}


class Arm:
    def __init__(self, a, truth, out):
        self.a, self.out = a, out
        self.oracle = Oracle(truth)
        self.floors = {q: DEFAULT_FLOOR for q in QIDS}
        if a.floors:
            self.floors.update(json.loads(Path(a.floors).read_text()))
        self.log = open(out / 'calls.jsonl', 'a') if out else None
        self.calls, self.errors_in_row = 0, 0
        self.replay, self.unsimulated = None, 0
        self.rule = getattr(a, 'rule', 'frozen')          # programmatic replays of step 7 runs keep the frozen rule
        # floor lock (16-floor-lock-preregistration.md): the frozen starting floors; learning never lowers these for
        # answers that other units rely on
        self.lock = json.loads((HERE / 'frozen' / 'floors-B.json').read_text()) if self.rule == 'invariant-lock' else None
        self.last_weak = False

    def ask(self, quarter, qid, cert_id, ab, text, cats):
        rec = dict(quarter=quarter, cert_id=cert_id, addback_no=ab['addback_no'], qid=qid, backend=self.a.backend)
        ans, env, err = None, {}, None
        if self.replay is not None:
            src = self.replay.get((quarter, cert_id, ab['addback_no'], qid))
            if src is None:
                self.unsimulated += 1; err = 'unsimulated'
            else:
                ans, err = src.get('answer'), src.get('error')
        elif self.a.backend == 'claude' and self.a.mode == 'live':
            from run_b import ask_claude
            prompt = BQ.claude_prompt(qid, text, cats)
            rec['prompt_sha256'] = hashlib.sha256(prompt.encode()).hexdigest()
            ans, env, err = ask_claude(prompt, self.a.model, self.a.deadline_s)
            self.calls += 1
            env = {k: env.get(k) for k in ('duration_ms', 'usage', 'total_cost_usd', 'modelUsage') if k in env}
            served = list((env.get('modelUsage') or {}).keys())
            if not err and served and self.a.model not in served:
                err = f'served model {served} is not the pinned {self.a.model}'
        else:
            ans = self.oracle.ask(qid, cert_id, ab['addback_no'], text, cats)
        value, top, p = NEEDS_REVIEW, None, None
        if err is None:
            try:
                value, top, p = BQ.decide(ans, qid, float(self.floors.get(qid, DEFAULT_FLOOR)), cats)
            except BQ.Shape as e:
                err = f'malformed: {e}'
        ev = (ans or {}).get('evidence', '')
        qok = err is None and BQ.quote_ok(qid, value, ev, text, ab['addback_no'])
        if not qok:
            value = NEEDS_REVIEW
        self.last_weak = bool(self.lock and value != NEEDS_REVIEW and p is not None and p < float(self.lock[qid]))
        rec.update(answer=ans, value=value, top=top, p_top=p, error=err, quote_ok=qok, envelope=env)
        if self.lock:
            rec['below_lock'] = self.last_weak
        if self.log and self.replay is None:
            self.log.write(json.dumps(rec, ensure_ascii=False) + '\n'); self.log.flush()
        self.errors_in_row = self.errors_in_row + 1 if err else 0
        if self.errors_in_row >= 3 and self.replay is None:
            raise SystemExit(f'STOP: 3 errors in a row; last: {err}')
        return value

    def certificate(self, quarter, cert, ag, cats, prior):
        judged, weak = {}, {}
        for ab in cert['addbacks']:
            n = ab['addback_no']
            qc = self.ask(quarter, 'QC', cert['cert_id'], ab, BQ.text_for('QC', ab), cats)
            if self.last_weak:
                weak.setdefault(n, set()).add('category')
            j = dict(category=qc, realized='n_a', certified='n_a')
            if qc == 'cost_savings':
                j['realized'] = self.ask(quarter, 'QR', cert['cert_id'], ab, BQ.text_for('QR', ab), cats)
                if self.last_weak:
                    weak.setdefault(n, set()).add('realized')
                j['certified'] = self.ask(quarter, 'QX', cert['cert_id'], ab, BQ.text_for('QX', ab, cert.get('certification_text')), cats)
                if self.last_weak:
                    weak.setdefault(n, set()).add('certified')
            judged[n] = j
        units, info = decide_certificate(cert, ag, prior, judged, cats, self.rule, weak)
        return units, judged, info


def decide_certificate(cert, ag, prior, judged, cats, rule, weak=None):
    """Code's decision on one certificate from its typed answers. rule 'invariant' is the pre-registered fix
    (bcode.evaluate_invariant); 'invariant-lock' adds the floor lock (weak answers, 16-floor-lock-preregistration.md);
    rule 'frozen' is the step 7 rule as frozen in FREEZE-BANK.json, kept verbatim for replay."""
    if rule == 'invariant':
        return B.evaluate_invariant(cert, ag, prior, judged, cats)
    if rule == 'invariant-lock':
        return B.evaluate_invariant(cert, ag, prior, judged, cats, weak)
    if rule != 'frozen':
        raise ValueError(f'unknown rule {rule!r}')
    units, info = B.evaluate(cert, ag, prior, judged)
    # a covenant whose breach status turns on an addback held for review is held too (fails closed)
    held_nr = [n for n, j in judged.items() if NEEDS_REVIEW in j.values()]
    if held_nr:
        alt = {n: (dict(category='ordinary_operating', realized='n_a', certified='n_a') if n in held_nr else j) for n, j in judged.items()}
        alt_units, _ = B.evaluate(cert, ag, prior, alt)
        for uid in ('LEV', 'ICR'):
            if uid in units and units[uid]['breach'] != alt_units[uid]['breach']:
                units[uid].update(disposition='hold', owner='required_lenders', review='breach_depends_on_review')
    return units, info


def run_quarters(arm, a, truth, quarters, labels=None, on_quarter=None):
    """-> {quarter: rows}. Used by the live run and by replays (floors sweep, learning step)."""
    keyu = {(u['cert_id'], u['unit_id']): u for u in truth['units']}
    out = {}
    for q in quarters:
        ags, cats, prior = load_ref(a.corpus, q)
        by_name = {g['borrower']: g for g in ags}
        rows = []
        for pdf in sorted((Path(a.corpus) / 'clean').glob(f'q{q}_*.pdf')):
            cid = pdf.stem
            want = sorted(uid for (c, uid) in keyu if c == cid)
            try:
                cert = BU.read_certificate(pdf, q)
                ag = by_name[cert['borrower']]
                cert['borrower_id'] = ag['borrower_id']
                units, judged, info = arm.certificate(q, cert, ag, cats, prior)
            except Exception as e:                                     # noqa: BLE001  unreadable: the person reads it
                rows += [dict(quarter=q, cert_id=cid, unit_id=uid, disposition='hold', owner='analyst',
                              error_class='unreadable', breach='no', reasons=[f'parse: {e}'[:200]]) for uid in want]
                continue
            for uid in want:
                u = units.get(uid)
                if u is None:
                    rows.append(dict(quarter=q, cert_id=cid, unit_id=uid, disposition='hold', owner='analyst',
                                     error_class='unit_not_found', breach='no', reasons=['parse: unit not read']))
                    continue
                rows.append(dict(quarter=q, cert_id=cid, unit_id=uid, disposition=u['disposition'], owner=u['owner'],
                                 error_class=u['error_class'], breach=u['breach'], reasons=[u['error_class']] + ([u['review']] if u.get('review') else []),
                                 judged=judged.get(int(uid[1:])) if uid.startswith('A') else None))
        out[q] = rows
        if on_quarter:
            on_quarter(q, rows)
    return out


def replay_index(calls_path):
    idx = {}
    for x in open(calls_path):
        c = json.loads(x)
        idx.setdefault((c['quarter'], c['cert_id'], c['addback_no'], c['qid']), c)
    return idx


def silent_held(rows, labels):
    s = sum(1 for r in rows if r['disposition'] == 'post' and labels.get((r['cert_id'], r['unit_id'])) == 'hold')
    return s, sum(1 for r in rows if r['disposition'] == 'hold')


def challenger(a, truth, quarters, calls_path, labels, running):
    """Step 6's promotion rule on the banking ledger: replay logged answers (no new calls) at candidate floors;
    promote only when every past quarter shows no new silent unit among labelled units and no more held, and
    fewer held in total."""
    idx = replay_index(calls_path)

    def ev(fl):
        arm = Arm(argparse.Namespace(**{**vars(a), 'floors': None}), truth, None)
        arm.floors, arm.replay = dict(fl), idx
        res = run_quarters(arm, a, truth, quarters)
        return {q: silent_held(res[q], labels) for q in quarters}
    base = ev(running); floors = dict(running)
    for _ in range(2):
        for q in QIDS:
            best = None
            for f in GRID:
                r = ev(dict(floors, **{q: f}))
                key = (sum(x[0] for x in r.values()), sum(x[1] for x in r.values()), -f)
                if best is None or key < best[0]:
                    best = (key, f)
            floors[q] = best[1]
    chal = ev(floors)
    ok = (all(chal[q][0] <= base[q][0] and chal[q][1] <= base[q][1] for q in quarters)
          and sum(c[1] for c in chal.values()) < sum(b[1] for b in base.values()))
    return dict(quarters=quarters, running=running, challenger=floors, running_replay={str(q): base[q] for q in quarters},
                challenger_replay={str(q): chal[q] for q in quarters}, promoted=ok,
                signed='Frank, 2026-10-08: promotion rule approved (auto when strictly better)' if ok else None), ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=str(DEMO / 'synth-bank'))
    ap.add_argument('--quarters', type=int, nargs='+', required=True)
    ap.add_argument('--backend', choices=('oracle', 'claude'), default='oracle')
    ap.add_argument('--mode', choices=('dry-run', 'live'), default='dry-run')
    ap.add_argument('--model'); ap.add_argument('--deadline-s', type=float, default=90.0)
    ap.add_argument('--floors'); ap.add_argument('--loop', action='store_true')
    ap.add_argument('--frozen'); ap.add_argument('--seed', type=int, default=7); ap.add_argument('--out')
    ap.add_argument('--rule', choices=('invariant', 'invariant-lock', 'frozen'), default='invariant',
                    help='invariant: the step 7b fix (13); invariant-lock: plus the floor lock (16); frozen: the step 7 rule')
    a = ap.parse_args()
    live = a.backend == 'claude' and a.mode == 'live'
    if live and not a.model:
        ap.error('claude live needs --model <exact id>')
    if a.backend == 'claude' and not live:
        ap.error('claude dry-run has nothing to answer with; use --backend oracle')
    if a.frozen:
        fz = json.loads(Path(a.frozen).read_text()); root = Path(a.frozen).resolve().parent
        bad = [f for f, h in fz['hashes'].items() if hashlib.sha256((root / f).read_bytes()).hexdigest() != h]
        if bad:
            sys.exit(f'REFUSED: frozen files changed since the freeze: {bad}')
        a.floors = str(root / fz['floors_file'])
    elif any(q > 2 for q in a.quarters) and live:
        sys.exit('REFUSED: quarters 3-4 run live only with --frozen bank/frozen/FREEZE-BANK.json')
    if not live:
        jev.install_socket_guard()
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    keyd = {(u['cert_id'], u['unit_id']): u['disposition'] for u in truth['units']}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    arm_name = f"D-bank-{a.backend}-{a.mode}-q{''.join(map(str, a.quarters))}-{stamp}"
    out = Path(a.out) if a.out else DEMO / 'runs' / 'bank' / arm_name
    if out.exists() and (out / 'calls.jsonl').exists():
        sys.exit(f'REFUSED: {out} already holds a run (D-301 (4): one folder per run)')
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(arm=arm_name, corpus=str(Path(a.corpus).resolve()), quarters=a.quarters, backend=a.backend, mode=a.mode,
                model=a.model if live else None, rule=a.rule, floors=a.floors or f'default {DEFAULT_FLOOR}', frozen=a.frozen, started=stamp,
                truth_sha256=hashlib.sha256((Path(a.corpus) / 'truth_q.json').read_bytes()).hexdigest())
    if live:
        from run_b import claude_version, claude_auth_method
        meta.update(claude_version=claude_version(), claude_auth_method=claude_auth_method())
    arm = Arm(a, truth, out)
    labels, done, promotions = {}, [], []
    t0 = time.time()

    def close(q, rows):
        (out / f'q{q}').mkdir(exist_ok=True)
        (out / f'q{q}' / 'outcomes.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False) + '\n')
        rng = random.Random(f'{a.seed}-{q}')
        posted = [r for r in rows if r['disposition'] == 'post']
        sample = rng.sample(posted, max(1, round(AUDIT_SHARE * len(posted)))) if posted else []
        found = [(s['cert_id'], s['unit_id']) for s in sample if keyd[(s['cert_id'], s['unit_id'])] == 'hold']
        (out / f'q{q}' / 'close.json').write_text(json.dumps(dict(quarter=q, posted=len(posted), held=len(rows) - len(posted),
            audit_n=len(sample), audit_found=found, audit_estimate_silent=round(len(found) / len(sample) * len(posted), 1) if sample else None), indent=1) + '\n')
        for r in rows:
            if r['disposition'] == 'hold':
                labels[(r['cert_id'], r['unit_id'])] = keyd[(r['cert_id'], r['unit_id'])]
        for s_ in sample:
            labels[(s_['cert_id'], s_['unit_id'])] = keyd[(s_['cert_id'], s_['unit_id'])]
        done.append(q)
        if a.loop:
            arm.log.flush()
            prop, ok = challenger(a, truth, list(done), out / 'calls.jsonl', labels, dict(arm.floors))
            promotions.append(dict(after_quarter=q, **prop))
            if ok:
                arm.floors = dict(prop['challenger'])
            (out / 'promotions.json').write_text(json.dumps(promotions, indent=1) + '\n')
    try:
        run_quarters(arm, a, truth, a.quarters, on_quarter=close)
    finally:
        arm.log.close()
        meta.update(finished=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                    wall_s=round(time.time() - t0, 1), live_calls=arm.calls, floors_at_end=arm.floors)
        (out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(json.dumps({k: meta[k] for k in ('arm', 'live_calls', 'wall_s', 'floors_at_end')}, indent=1)); print(f'outputs: {out}')


if __name__ == '__main__':
    main()
