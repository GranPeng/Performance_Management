#!/usr/bin/env python3
"""T11c helper: compare two snapshot files by Result_ID; report Monthly_Total deltas."""
import json, sys
from collections import Counter

base_path, run_path = sys.argv[1], sys.argv[2]
base = {r["Result_ID"]: r for r in json.load(open(base_path, encoding="utf-8"))}
run = {r["Result_ID"]: r for r in json.load(open(run_path, encoding="utf-8"))}

print("base rows:", len(base), "| run rows:", len(run))
missing = [k for k in base if k not in run]
extra = [k for k in run if k not in base]
print("missing in run:", len(missing), missing[:5])
print("extra in run:", len(extra), extra[:5])

deltas = []
for k in base:
    if k not in run:
        continue
    b_mt = base[k].get("Monthly_Total")
    r_mt = run[k].get("Monthly_Total")
    try:
        bf = float(b_mt) if b_mt not in (None, "") else None
    except (TypeError, ValueError):
        bf = None
    try:
        rf = float(r_mt) if r_mt not in (None, "") else None
    except (TypeError, ValueError):
        rf = None
    if bf != rf:
        deltas.append({"Result_ID": k, "base": b_mt, "run": r_mt})
print("Monthly_Total deltas:", len(deltas))
for d in deltas[:10]:
    print(json.dumps(d, ensure_ascii=False))

# Commission_Amount manual recheck samples
print("\nCommission_Amount non-null:", sum(1 for r in run.values() if r.get("Commission_Amount") not in (None, "")))
# distribution of commission base type
print("Base_Type:", dict(Counter(str(r.get("Commission_Base_Type")) for r in run.values() if r.get("Commission_Base_Type"))))
