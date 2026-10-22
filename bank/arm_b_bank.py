#!/usr/bin/env python3
"""Step 7 arm B, banking: one agent reads a quarter's 12 certificates with the agreements and lists every unit to
hold, with its owner. Step 6's strongest single-agent design: a worksheet first, plus the calculator tool.

  arm_b_bank.py --quarters 1 2 --backend oracle
  arm_b_bank.py --quarters 3 4 --backend claude --mode live --model claude-sonnet-5-5 --frozen bank/frozen/FREEZE-BANK.json

Reused unchanged from step 6: month/arm_b.py (claude_stream, calc_args), month/calc_mcp.py, month/arms_common.py
(doc_text). The policy text is the key's own definitions (rekey_fields_q.md, the "Definitions" and label tables),
so the agent gets exactly the rules the key applies. One call per quarter; a failed call is retried twice, then the
quarter fails closed (every unit held).
"""
import argparse, datetime, hashlib, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
sys.path.insert(0, str(DEMO / 'month')); sys.path.insert(0, str(DEMO / 'jobb')); sys.path.insert(0, str(DEMO / 'typed'))
import arm_b as MB  # noqa: E402  (step 6 runner: claude_stream, calc_args)
import arms_common as AC  # noqa: E402

RULES = DEMO.parent / 'artifacts' / 'one-loop-step7-2026-10-08' / 'inputs' / 'rekey_fields_q.md'
SYSTEM = MB.SYSTEM_CALC.replace('joint-interest billing month', 'quarter of compliance certificates')
ISSUES = ['ratio_arithmetic', 'hidden_breach', 'reported_breach', 'cap_exceeded', 'window_expired', 'category_not_permitted',
          'certification_missing', 'signer_not_officer', 'late_delivery', 'cure_invalid', 'duplicate_addback', 'needs_review']


def policy():
    t = RULES.read_text()
    i, j = t.index('## Definitions'), t.index('## Output')
    return t[i:j].replace('by eye, from the page images', 'from the certificate text')


def prompt_for(corpus, q, units_by_cert):
    ref = Path(corpus) / 'reference'
    refs = '\n'.join(f'{n}: ' + (ref / n).read_text().strip() for n in ('agreements.json', 'categories.json', f'prior_cures_q{q}.json'))
    docs = '\n\n'.join(f'==== Certificate {p.stem} (units: {", ".join(units_by_cert[p.stem])}) ====\n{AC.doc_text(p)}'
                       for p in sorted((Path(corpus) / 'clean').glob(f'q{q}_*.pdf')))
    return ('You review one quarter of compliance certificates for the bank, as Administrative Agent. Hold a unit for a '
            'person when the definitions below give it an error class, or a breach; post it otherwise. Name the owner '
            'by the owner rule.\n\n' + policy() + f'\nQuarter under review: 2025 Q{q}.\n\nReference data:\n{refs}\n\n'
            + 'Work in two passes. First fill a worksheet with one row per unit of every certificate, as one pipe-separated '
            'string: cert_id|unit_id|every value you read from the page for this unit|every value you looked up in the '
            'agreement|your computation|error class or none|breach yes/no. Read each value from the page; never carry a '
            'value from another row, unit, or borrower. Then list the units to hold.\n'
            + '\nYou have one tool, calculate, which evaluates arithmetic exactly. Use it for every sum, ratio, cap, and '
            'date-window computation. Do not do arithmetic in your head.\n'
            + '\nReturn {"worksheet": [<one string per unit>], "holds": [{"cert_id": ..., "unit_id": ..., '
            f'"issue": <one of {json.dumps(ISSUES)}>, "breach": "yes"|"no", "owner": "required_lenders"|"credit_officer"|"analyst"}}]}}. '
            'List every unit to hold, once. Units you do not list are posted.\n\n' + docs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=str(DEMO / 'synth-bank'))
    ap.add_argument('--quarters', type=int, nargs='+', required=True)
    ap.add_argument('--backend', choices=('oracle', 'claude'), default='oracle')
    ap.add_argument('--mode', choices=('dry-run', 'live'), default='dry-run')
    ap.add_argument('--model'); ap.add_argument('--deadline-s', type=float, default=3600.0)
    ap.add_argument('--frozen'); ap.add_argument('--out'); ap.add_argument('--dump-prompts', action='store_true')
    a = ap.parse_args()
    live = a.backend == 'claude' and a.mode == 'live'
    if live and not a.model:
        ap.error('live needs --model')
    if live and any(q > 2 for q in a.quarters):
        if not a.frozen:
            sys.exit('REFUSED: quarters 3-4 run live only with --frozen bank/frozen/FREEZE-BANK.json')
        fz = json.loads(Path(a.frozen).read_text()); root = Path(a.frozen).resolve().parent
        bad = [f for f, h in fz['hashes'].items() if hashlib.sha256((root / f).read_bytes()).hexdigest() != h]
        if bad:
            sys.exit(f'REFUSED: frozen files changed since the freeze: {bad}')
    truth = json.loads((Path(a.corpus) / 'truth_q.json').read_text())
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = f"B-bank-{a.backend}-{a.mode}-q{''.join(map(str, a.quarters))}-{stamp}"
    out = Path(a.out) if a.out else DEMO / 'runs' / 'bank' / name
    if (out / 'calls.jsonl').exists():
        sys.exit(f'REFUSED: {out} already holds a run (D-301 (4))')
    out.mkdir(parents=True, exist_ok=True)
    meta = dict(arm=name, quarters=a.quarters, backend=a.backend, mode=a.mode, model=a.model if live else None, frozen=a.frozen,
                design='worksheet + calculator (step 6 strongest)', started=stamp, quarters_failed_closed=[])
    log = open(out / 'calls.jsonl', 'a'); t0 = time.time()
    try:
        for q in a.quarters:
            units = sorted((u for u in truth['units'] if u['quarter'] == q), key=lambda u: (u['cert_id'], u['unit_id']))
            by_cert = {}
            for u in units:
                by_cert.setdefault(u['cert_id'], []).append(u['unit_id'])
            prompt = prompt_for(a.corpus, q, by_cert)
            if a.dump_prompts:
                (out / f'prompt-q{q}.txt').write_text(prompt); print(f'q{q}: {len(prompt)} chars'); continue
            rec = dict(quarter=q, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), prompt_chars=len(prompt))
            ans, err, attempts = None, None, 0
            if live:
                for attempts in range(1, 4):
                    ans, env, err = MB.claude_stream(prompt, a.model, a.deadline_s, SYSTEM, MB.calc_args(out, q))
                    ok, served = AC.served_ok(env, a.model)
                    if not err and not ok:
                        err = f'served model {served} is not the pinned {a.model}'
                    if not err and not isinstance((ans or {}).get('holds'), list):
                        err = 'no holds list'
                    rec.setdefault('envelopes', []).append(dict(AC.slim_env(env), error=err, **{k: env[k] for k in ('init', 'tool_uses') if k in env}))
                    if not err:
                        break
            else:
                ans = {'holds': [dict(cert_id=u['cert_id'], unit_id=u['unit_id'], issue=u['error_class'], breach=u['breach'], owner=u['owner'])
                                 for u in units if u['disposition'] == 'hold']}
            if err:
                rows = [dict(quarter=q, cert_id=u['cert_id'], unit_id=u['unit_id'], disposition='hold', owner='analyst', breach='no',
                             reasons=['agent:failed_closed']) for u in units]
                meta['quarters_failed_closed'].append(q)
            else:
                holds = {}
                for h in ans.get('holds', []):
                    try:
                        holds[(str(h['cert_id']).strip(), str(h['unit_id']).strip().upper())] = h
                    except (KeyError, TypeError):
                        continue
                rows = []
                for u in units:
                    h = holds.get((u['cert_id'], u['unit_id']))
                    rows.append(dict(quarter=q, cert_id=u['cert_id'], unit_id=u['unit_id'], disposition='hold' if h else 'post',
                                     owner=(h or {}).get('owner', 'none'), breach=(h or {}).get('breach', 'no'),
                                     reasons=['agent:' + str((h or {}).get('issue'))] if h else []))
                rec['named_not_a_unit'] = [k for k in holds if k not in {(u['cert_id'], u['unit_id']) for u in units}]
            rec.update(answer=ans, error=err, attempts=attempts)
            log.write(json.dumps(rec, ensure_ascii=False) + '\n'); log.flush()
            (out / f'q{q}').mkdir(exist_ok=True)
            (out / f'q{q}' / 'outcomes.json').write_text(json.dumps(rows, indent=1) + '\n')
            print(f"q{q}: held {sum(r['disposition'] == 'hold' for r in rows)}, error {err}", flush=True)
    finally:
        log.close()
        meta.update(finished=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'), wall_s=round(time.time() - t0, 1))
        (out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(f'outputs: {out}')


if __name__ == '__main__':
    main()
