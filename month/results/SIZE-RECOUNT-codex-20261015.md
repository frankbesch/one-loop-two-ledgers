**The independent recount found three silent errors, all in d24; all model, attempt, and key-set checks passed.**

## Recount by run-set

Counts aggregate months m3–m6. “Money caught” means a planted money-error line was held. Every caught line also carried its matching money-error class.

| Size | Round | Silent errors | Held | False holds | Money caught / total | Silent P | Silent D |
|---|---:|---:|---:|---:|---:|---:|---:|
| d3 | 1 | 0 | 14 | 0 | 12 / 12 | 0 | 0 |
| d3 | 2 | 0 | 14 | 0 | 12 / 12 | 0 | 0 |
| d3 | 3 | 0 | 14 | 0 | 12 / 12 | 0 | 0 |
| d3 | 4 | 0 | 14 | 0 | 12 / 12 | 0 | 0 |
| d3 | 5 | 0 | 14 | 0 | 12 / 12 | 0 | 0 |
| d6 | 1 | 0 | 31 | 0 | 24 / 24 | 0 | 0 |
| d6 | 2 | 0 | 31 | 0 | 24 / 24 | 0 | 0 |
| d6 | 3 | 0 | 31 | 0 | 24 / 24 | 0 | 0 |
| d6 | 4 | 0 | 31 | 0 | 24 / 24 | 0 | 0 |
| d6 | 5 | 0 | 31 | 0 | 24 / 24 | 0 | 0 |
| d12 | 1 | 0 | 71 | 0 | 49 / 49 | 0 | 0 |
| d12 | 2 | 0 | 71 | 0 | 49 / 49 | 0 | 0 |
| d12 | 3 | 0 | 71 | 0 | 49 / 49 | 0 | 0 |
| d12 | 4 | 0 | 71 | 0 | 49 / 49 | 0 | 0 |
| d12 | 5 | 0 | 71 | 0 | 49 / 49 | 0 | 0 |
| d24 | 1 | 0 | 148 | 0 | 96 / 96 | 0 | 0 |
| d24 | 2 | 1 | 148 | 1 | 95 / 96 | 0 | 0 |
| d24 | 3 | 0 | 148 | 0 | 96 / 96 | 0 | 0 |
| d24 | 4 | 1 | 147 | 0 | 95 / 96 | 0 | 0 |
| d24 | 5 | 1 | 149 | 2 | 96 / 96 | 0 | 0 |

### Worst run on P

“Worst” means the maximum cumulative silent-P count across months m3–m6, compared across rounds.

| Size | Maximum silent P | Tied rounds | P keys exposed / fixed set | D keys exposed / fixed set |
|---|---:|---|---:|---:|
| d3 | 0 | 1, 2, 3, 4, 5 | 10 / 23 | 4 / 8 |
| d6 | 0 | 1, 2, 3, 4, 5 | 23 / 23 | 8 / 8 |
| d12 | 0 | 1, 2, 3, 4, 5 | 23 / 23 | 8 / 8 |
| d24 | 0 | 1, 2, 3, 4, 5 | 23 / 23 | 8 / 8 |

The d3 result covers only its exposed target keys. The d24 silent errors fall outside both fixed target sets.

## Every silent occurrence

| Run-set | Document | Line | Truth `money_error` | Truth `error_dollars` |
|---|---|---:|---|---:|
| SIZE-d24-r2 | m3_jib_12 | 1 | wrong_decimal | 38.18 |
| SIZE-d24-r4 | m3_jib_12 | 1 | wrong_decimal | 38.18 |
| SIZE-d24-r5 | m6_jib_07 | 3 | none | 0 |

Every other run-set has no silent keys. The `none` class still requires a hold under the truth disposition.

## Decimal-line evidence

The worksheet’s decimal order is interpreted as owner decimal in force, then printed decimal, consistent with truth and exception evidence. The supplied rows have no headers.

Exact rows for `m3_jib_12`, line `1`:

```text
SIZE-d24-r1:
m3_jib_12|1|LX/874/P|0.0875|0.1125|-|-|consent|-|-|-|yes|none

SIZE-d24-r2:
m3_jib_12|1|LX/874/P|0.0875|0.0875|-|-|consent|-|-|-|yes|none

SIZE-d24-r3:
m3_jib_12|1|LX/874/P|0.0875|0.1125|-|-|consent|-|-|-|yes|none

SIZE-d24-r4:
m3_jib_12|1|LX/874/P|0.0875|0.0875|-|-|consent|-|-|-|yes|none

SIZE-d24-r5:
m3_jib_12|1|LX/874/P|0.0875|0.1125|-|-|consent|-|-|-|yes|none
```

| Run-set | Printed cell | In-force cell | Exception for this line | Outcome | Classification |
|---|---:|---:|---|---|---|
| SIZE-d24-r1 | 0.1125 | 0.0875 | `wrong_decimal` | hold | Not silent |
| SIZE-d24-r2 | 0.0875 | 0.0875 | None | post | **(a) misread** |
| SIZE-d24-r3 | 0.1125 | 0.0875 | `wrong_decimal` | hold | Not silent |
| SIZE-d24-r4 | 0.0875 | 0.0875 | None | post | **(a) misread** |
| SIZE-d24-r5 | 0.1125 | 0.0875 | `wrong_decimal` | hold | Not silent |

Each listed exception quotes `"0.1125"` and records `dollars_at_stake: 171.8`. That exception amount differs from truth `error_dollars: 38.18`.

Calculator searches covered every `calc-m3-a*.jsonl` file in each run. These are all matching calls:

| Run-set | Contains `0.1125` | Contains `0.0875` | Matching expression → result |
|---|---|---|---|
| SIZE-d24-r1 | Yes | No | `round(1527.11*0.1125,2)` → `171.80` |
| SIZE-d24-r2 | Yes | No | `0.1375-0.1125` → `0.0250` |
| SIZE-d24-r3 | No | Yes | `737.5*0.0875` → `64.53125` |
| SIZE-d24-r4 | Yes | No | `0.1375-0.1125` → `0.0250` |
| SIZE-d24-r5 | Yes | No | `round(1527.11*0.1125,2)` → `171.80` |

The silent runs’ matching expression does not compare this line’s printed and in-force decimals. Classification **(a)** follows the recorded printed cell; it does not establish the internal cause.

## Integrity checks

- All 80 monthly call records across 20 run-sets have exactly `["claude-sonnet-5-5"]` in `envelopes[-1].modelUsage` keys.
- Every monthly record has `attempts == 1`, and every run-set contains exactly the expected monthly records.
- All 7,860 worksheet rows match packet line sets, with no missing, extra, duplicate, or unparsed keys.
- All 7,860 outcome rows match packet line sets, with no missing, extra, or duplicate keys.
- No run-set contains `VOID.txt`, and every `months_failed_closed` list is empty.

I read no scorer, modified no files, and ran no git commands.

## Executed recount command

This command independently derives expected line sets from truth lines and packet document membership. It ignores supplied summary counts and worksheet-validation fields.

```bash
python3 -c 'import json,re
from pathlib import Path
from collections import Counter
def read(p): return json.loads(Path(p).read_text())
def key(r): return (r["doc_id"],r["line_no"])
truth=read("truth_m.json")["lines"]
T={key(r):r for r in truth}
assert len(T)==len(truth)
packets=read("packets.json")["sizes"]
targets=read("targets.json")
P,D=({tuple(k) for k in targets[n]} for n in ("P","D"))
results=[]; issues=[]; checks=Counter()
for size in ("d3","d6","d12","d24"):
 for rnd in range(1,6):
  run=Path(f"runs/SIZE-{size}-r{rnd}")
  meta=read(run/"meta.json")
  calls=[json.loads(s) for s in (run/"calls.jsonl").read_text().splitlines()]
  assert Counter(c["month"] for c in calls)==Counter(range(3,7))
  voids=list(run.rglob("VOID.txt"))
  if voids or meta.get("months_failed_closed"): issues.append([run.name,"flags",str(voids),meta.get("months_failed_closed")])
  silent=set(); held=set(); allkeys=set(); tagged=0
  for month in range(3,7):
   docs=set(packets[size][f"m{month}"])
   expected={k for k,t in T.items() if t["month"]==month and k[0] in docs}
   assert {k[0] for k in expected}==docs
   allkeys |= expected
   outcomes=read(run/f"m{month}"/"outcomes.json")
   oc=Counter(key(o) for o in outcomes)
   if set(oc)!=expected or any(v!=1 for v in oc.values()): issues.append([run.name,month,"outcomes",sorted(expected-set(oc)),sorted(set(oc)-expected),[k for k,v in oc.items() if v>1]])
   for o in outcomes:
    k=key(o)
    assert o["disposition"] in ("post","hold")
    if k not in expected: continue
    if o["disposition"]=="hold":
     held.add(k)
     tagged += T[k]["money_error"]!="none" and T[k]["money_error"] in o.get("money",[])
    elif T[k]["disposition"]=="hold": silent.add(k)
   c=next(c for c in calls if c["month"]==month)
   models=list(c["envelopes"][-1]["modelUsage"])
   if models!=["claude-sonnet-5-5"] or c["attempts"]!=1: issues.append([run.name,month,"model/attempts",models,c["attempts"]])
   checks["calls"]+=1
   wc=Counter(); unparsed=[]
   for row in c["answer"]["worksheet"]:
    if not isinstance(row,str): unparsed.append(row); continue
    fields=row.split("|")
    if len(fields)<2 or not re.fullmatch(r"m[0-9]+_(?:inv|jib)_[0-9]+",fields[0]) or not re.fullmatch(r"[0-9]+",fields[1]):
     unparsed.append(row); continue
    wc[(fields[0],int(fields[1]))]+=1
   missing=sorted(expected-set(wc)); extra=sorted(set(wc)-expected); dupes=[k for k,v in wc.items() if v>1]
   if missing or extra or dupes or unparsed: issues.append([run.name,month,"worksheet",missing,extra,dupes,unparsed])
   checks["worksheet_rows"]+=sum(wc.values())
   checks["outcome_rows"]+=len(outcomes)
  money={k for k in allkeys if T[k]["money_error"]!="none"}
  result=dict(size=size,round=rnd,silent=len(silent),held=len(held),false_holds=sum(T[k]["disposition"]=="post" for k in held),money_caught=len(money&held),money_total=len(money),money_class_tagged=tagged,P=len(silent&P),D=len(silent&D))
  results.append(result)
  print("RUN",json.dumps(result))
  print("SILENT",run.name,json.dumps([dict(doc_id=k[0],line_no=k[1],money_error=T[k]["money_error"],error_dollars=T[k]["error_dollars"]) for k in sorted(silent)]))
  if size=="d24":
   c=next(c for c in calls if c["month"]==3)
   rows=[r for r in c["answer"]["worksheet"] if r.startswith("m3_jib_12|1|")]
   exceptions=[e for e in c["answer"]["exceptions"] if key(e)==("m3_jib_12",1)]
   calc=[json.loads(s) for f in sorted(run.glob("calc-m3-a*.jsonl")) for s in f.read_text().splitlines()]
   matches=[x for x in calc if "0.1125" in json.dumps(x) or "0.0875" in json.dumps(x)]
   print("FOCUS",json.dumps(dict(run=run.name,rows=rows,exceptions=exceptions,silent=("m3_jib_12",1) in silent,calc_count=len(calc),calc_matches=matches)))
for size in packets:
 rows=[r for r in results if r["size"]==size]; worst=max(r["P"] for r in rows)
 keys={k for k,t in T.items() if any(k[0] in docs for docs in packets[size].values())}
 print("SIZE",size,"worst_P",worst,"rounds",[r["round"] for r in rows if r["P"]==worst],"P_exposed",len(keys&P),"D_exposed",len(keys&D))
print("CHECKS",dict(checks),"ISSUES",json.dumps(issues))
print("TOTAL_SILENT",sum(r["silent"] for r in results),"TARGET_COUNTS",len(P),len(D),"RUNS",len(results))
'
```