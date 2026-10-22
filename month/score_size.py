#!/usr/bin/env python3
"""Packet-size test scorer (publishing one-loop-two-ledgers/18-packet-size-preregistration.md v2 §3-4).

  score_size.py [--results results] [--tag SIZE] [--targets packets/targets.json] [--adjudication packets/h48-adjudication.json]
                [--out results/SIZE-summary.json]

Per run-set: status (void / invalid / incomplete / complete), whole-packet counts from score.json, and on the fixed
target sets S6, P, D: silent, held, false holds, money caught (count, dollars, right reason) from outcomes.json
against truth; worksheet identity coverage from calls.jsonl. Per size: the counted run-sets (first five complete,
non-void, rounds 1-8 in round order), the worst run on P, H45-H49 exactly as written. H48 reads an optional
adjudication file {"<folder>:<doc_id>:<line_no>": "a"|"b"|"c"|"d"|"e"} written by hand after the runs.
Unknown top-level keys in any input file are ignored; sidecar data never lands in a case file.
"""
import argparse, json, math, re
from collections import Counter
from pathlib import Path

SIZES = ['d3', 'd6', 'd12', 'd24']
CLAIM_SIZES = ['d6', 'd12', 'd24']
MAX_ROUND = 8


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def load_outcomes(d):
    """-> (rows by key, problems). A duplicate key or an unreadable month is a problem."""
    res, problems = {}, []
    months = sorted(p for p in d.glob('m[0-9]') if (p / 'outcomes.json').exists())
    if [m.name for m in months] != ['m3', 'm4', 'm5', 'm6']:
        problems.append(f'months present: {[m.name for m in months]}')
    for m in months:
        for r in json.loads((m / 'outcomes.json').read_text()):
            k = (r['doc_id'], r['line_no'])
            if k in res:
                problems.append(f'duplicate outcome {k}')
            res[k] = r
    return res, problems


def run_status(d, meta, packet_keys, res, problems, calls):
    if (d / 'VOID.txt').exists():
        return 'void'
    if not meta.get('finished') or not (d / 'score.json').exists():
        return 'invalid: unfinished or unscored'
    if problems:
        return 'invalid: ' + '; '.join(problems[:3])
    if set(res) != packet_keys:
        return f'invalid: outcome keys differ from the packet ({len(set(res) ^ packet_keys)} keys)'
    if sorted(c.get('month') for c in calls) != [3, 4, 5, 6]:
        return f'invalid: calls records for months {sorted(c.get("month") for c in calls)}'
    if meta.get('months_failed_closed'):
        return 'incomplete'
    return 'complete'


def set_counts(keys, res, truth, label):
    silent = [k for k in keys if res[k]['disposition'] == 'post' and truth[k]['disposition'] == 'hold']
    held = [k for k in keys if res[k]['disposition'] == 'hold']
    false_hold = [k for k in held if truth[k]['disposition'] == 'post']
    money = [k for k in keys if truth[k]['money_error'] != 'none']
    caught = [k for k in money if res[k]['disposition'] == 'hold']
    right = [k for k in caught if truth[k]['money_error'] in (res[k].get('money') or [])]
    return dict(n=len(keys), silent=len(silent), held=len(held), false_hold=len(false_hold), money_targets=len(money),
                money_caught=len(caught), money_right_reason=len(right),
                money_dollars_total=round(sum(truth[k]['error_dollars'] for k in money), 2),
                money_dollars_caught=round(sum(truth[k]['error_dollars'] for k in caught), 2),
                silent_keys=[list(k) for k in silent],
                silent_classes=dict(Counter(label(k) for k in silent)))


def score_run(d, truth, sets, packets, folder_size):
    if (d / 'VOID.txt').exists():
        return dict(folder=d.name, packet_size=folder_size, status='void', void=(d / 'VOID.txt').read_text()[:300])
    try:
        meta = json.loads((d / 'meta.json').read_text()) if (d / 'meta.json').exists() else {}
        res, problems = load_outcomes(d)
        calls = [json.loads(l) for l in (d / 'calls.jsonl').read_text().splitlines() if l.strip()] if (d / 'calls.jsonl').exists() else []
    except (ValueError, OSError, KeyError, TypeError) as ex:
        return dict(folder=d.name, packet_size=folder_size, status=f'invalid: unreadable artifact ({type(ex).__name__}: {str(ex)[:80]})')
    size = meta.get('packet_size')
    if size != folder_size:
        problems.append(f'meta packet_size {size!r} differs from the folder size {folder_size!r}')
    bad_disp = [k for k, r in res.items() if r.get('disposition') not in ('hold', 'post')]
    if bad_disp:
        problems.append(f'{len(bad_disp)} outcomes with a disposition other than hold/post')
    packet_keys = {k for k in truth if k[0] in {x for m in packets['sizes'].get(size, {}).values() for x in m}} if size else set()
    label = lambda k: truth[k]['money_error'] if truth[k]['money_error'] != 'none' else 'claim'
    out = dict(folder=d.name, packet_size=size, status=run_status(d, meta, packet_keys, res, problems, calls),
               model=meta.get('model'), claude_version=meta.get('claude_version'), wall_s=meta.get('wall_s'),
               months_failed_closed=meta.get('months_failed_closed'))
    if out['status'] in ('complete', 'incomplete'):
        out['whole'] = set_counts(sorted(packet_keys), res, truth, label)
        for name, keys in sets.items():
            out[name] = set_counts([k for k in keys if k in packet_keys], res, truth, label)
        out['months'] = [dict(month=c['month'], prompt_chars=c.get('prompt_chars'), attempts=c.get('attempts'), error=c.get('error'),
                              packet_lines=c.get('packet_lines'), worksheet_rows=c.get('worksheet_rows'),
                              worksheet_missing=c.get('worksheet_missing'), worksheet_extra=c.get('worksheet_extra'),
                              worksheet_dupes=c.get('worksheet_dupes'), worksheet_unparsed=c.get('worksheet_unparsed'),
                              tool_uses=sum((e.get('tool_uses') or 0) for e in (c.get('envelopes') or [])),
                              tool_uses_per_100_lines=round(100 * sum((e.get('tool_uses') or 0) for e in (c.get('envelopes') or [])) / c['packet_lines'], 2) if c.get('packet_lines') else None,
                              wall_ms=sum((e.get('duration_ms') or 0) for e in (c.get('envelopes') or []))) for c in calls]
        cov = out['months']
        for x in cov:  # H49 attribution: do missing worksheet rows carry planted errors or holds?
            miss = [tuple(k) for k in (x['worksheet_missing'] or [])]
            x['worksheet_missing_labels'] = {f'{k[0]}:{k[1]}': label(k) if truth[k]['disposition'] == 'hold' else 'clean' for k in miss if k in truth}
        out['worksheet_ok'] = (len(cov) == 4 and all(isinstance(x['worksheet_rows'], int) and x['worksheet_missing'] == [] and x['worksheet_extra'] == []
                                                     and x['worksheet_dupes'] == 0 and x['worksheet_unparsed'] == 0 for x in cov))
        out['m3_jib_12_1'] = res.get(('m3_jib_12', 1), {}).get('disposition')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', default='results'); ap.add_argument('--tag', default='SIZE')
    ap.add_argument('--targets', default='packets/targets.json'); ap.add_argument('--packets', default='packets/packets.json')
    ap.add_argument('--adjudication', default='packets/h48-adjudication.json'); ap.add_argument('--out')
    ap.add_argument('--corpus', default='../synth-month')
    a = ap.parse_args()
    truth = {(l['doc_id'], l['line_no']): l for l in json.loads((Path(a.corpus) / 'truth_m.json').read_text())['lines']}
    tg = json.loads(Path(a.targets).read_text()); packets = json.loads(Path(a.packets).read_text())
    sets = {k: [tuple(x) for x in tg[k]] for k in ('S6', 'S6_holds', 'P', 'D')}
    nP = tg['counts']['P']
    runs, out_of_range = {}, []
    for d in sorted(Path(a.results).glob(f'{a.tag}-d*-r*')):
        m = re.fullmatch(rf'{a.tag}-(d\d+)-r(\d+)', d.name)
        if not m or not d.is_dir():
            continue
        r = int(m.group(2))
        if r < 1 or r > MAX_ROUND:
            out_of_range.append(d.name); continue
        runs.setdefault(m.group(1), []).append((r, d))
    rep = dict(tag=a.tag, targets=tg['counts'], excluded_round_out_of_range=out_of_range, sizes={}, claims={})
    if out_of_range:
        print('EXCLUDED (round outside 1-8, pre-registration §4):', out_of_range)
    for s in SIZES:
        scored = [dict(score_run(d, truth, sets, packets, s), round=r) for r, d in sorted(runs.get(s, []))]
        counted = [x for x in scored if x['status'] == 'complete'][:5]
        worst = max(counted, key=lambda x: (x['P']['silent'], x['whole']['silent']), default=None)
        kP = sum(x['P']['silent'] for x in counted); nP_s = sum(x['P']['n'] for x in counted)
        rep['sizes'][s] = dict(run_sets=[dict(round=x['round'], folder=x['folder'], status=x['status']) for x in scored],
                               counted=[x['folder'] for x in counted], n_counted=len(counted), shortfall=max(0, 5 - len(counted)),
                               worst_P_silent=worst['P']['silent'] if worst else None, worst_folder=worst['folder'] if worst else None,
                               worst_tie_break='whole-packet silent, then first in round order',
                               worst_whole_silent=max((x['whole']['silent'] for x in counted), default=None),
                               P_rate=[kP, nP_s], P_wilson=wilson(kP, nP_s), runs=scored)
    S = rep['sizes']
    w = {s: S[s]['worst_P_silent'] for s in CLAIM_SIZES}
    short = {s: S[s]['shortfall'] for s in CLAIM_SIZES if S[s]['shortfall']}
    if all(v is not None for v in w.values()):
        rep['claims']['H45'] = dict(worst_P=w, result='PASS' if (w['d6'] <= w['d12'] <= w['d24'] and w['d6'] < w['d24']) else 'FAIL', shortfall=short)
    else:
        rep['claims']['H45'] = dict(worst_P=w, result='UNAVAILABLE: a size has no counted run-set', shortfall=short)
    for name, s, pred in (('H46', 'd6', lambda v: all(x == 0 for x in v)), ('H47', 'd24', lambda v: any(x >= 1 for x in v))):
        v = [x['whole']['silent'] for x in S[s]['runs'] if x['status'] == 'complete'][:5]
        rep['claims'][name] = dict(silent_per_run=v, shortfall=S[s]['shortfall'],
                                   result=('UNAVAILABLE: no counted run-set' if not v else 'PASS' if pred(v) else 'FAIL'))
    # H48: every silent planted money error on the whole packet, counted run-sets at d6/d12/d24
    silent_money = []
    for s in CLAIM_SIZES:
        for x in [r for r in S[s]['runs'] if r['status'] == 'complete'][:5]:
            for k in x['whole']['silent_keys']:
                if truth[tuple(k)]['money_error'] != 'none':
                    silent_money.append(dict(size=s, folder=x['folder'], key=f'{k[0]}:{k[1]}', cls=truth[tuple(k)]['money_error'],
                                             error_dollars=truth[tuple(k)]['error_dollars']))
    adj = json.loads(Path(a.adjudication).read_text()) if Path(a.adjudication).exists() else {}
    for e in silent_money:
        e['category'] = adj.get(f"{e['folder']}:{e['key']}")
    if any(S[s]['n_counted'] == 0 for s in CLAIM_SIZES):
        h48 = 'UNAVAILABLE: a claim size has no counted run-set'
    elif not silent_money:
        h48 = 'NOT EVALUATED: no silent planted money error in the counted run-sets'
    elif any(e['category'] is None for e in silent_money):
        h48 = 'PENDING: adjudicate every item in silent_money (categories a-e) in ' + a.adjudication
    elif any(e['category'] not in ('a', 'b', 'c', 'd', 'e') for e in silent_money):
        h48 = 'PENDING: an adjudication value is not one of a-e'
    else:
        h48 = 'PASS' if all(e['category'] in ('a', 'b') for e in silent_money) else 'FAIL'
    rep['claims']['H48'] = dict(result=h48, silent_money=silent_money)
    ws = {s: [x['worksheet_ok'] for x in S[s]['runs'] if x['status'] == 'complete'][:5] for s in CLAIM_SIZES}
    rep['claims']['H49'] = dict(worksheet_ok=ws, result=('UNAVAILABLE' if not all(ws.values()) else 'PASS' if all(all(v) for v in ws.values()) else 'FAIL'))
    print(f"{'size':<5}{'counted':>8}{'worstP':>8}{'worst':>7}{'P k/n':>10}{'silent per run':>20}  {'held per run'}")
    for s in SIZES:
        x = S[s]; rc = [r for r in x['runs'] if r['status'] == 'complete'][:5]
        print(f"{s:<5}{x['n_counted']:>8}{str(x['worst_P_silent']):>8}{str(x['worst_whole_silent']):>7}{str(x['P_rate']):>10}"
              f"{str([r['whole']['silent'] for r in rc]):>20}  {[r['whole']['held'] for r in rc]}")
        for r in x['runs']:
            if r['status'] != 'complete':
                print(f'      {r["folder"]}: {r["status"]}')
    for k, v in rep['claims'].items():
        print(k, v['result'], {kk: vv for kk, vv in v.items() if kk not in ('result', 'silent_money')})
    out = Path(a.out) if a.out else Path(a.results) / f'{a.tag}-summary.json'
    out.write_text(json.dumps(rep, indent=1) + '\n'); print('->', out)


if __name__ == '__main__':
    main()
