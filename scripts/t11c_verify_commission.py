#!/usr/bin/env python3
"""T11c manual commission recheck per business_rules.md §3.

Rules:
- 运营族 (OPS/SUP): Commission_Ratio = Commission_Tier.Base_Rate × Commission_Tier.Coefficient（按 Monthly_Total 命中梯度）
- 主播/内容部/广告: Commission_Ratio = Commission_Tier.Ratio_Value
- Commission_Amount = Commission_Base × Commission_Ratio
Base = Actual_Value of the position's base metric (D-009): GSV (OPS-001/SUP-001), 个人消耗 (DIR-003/EDIT-003),
      个人营收 (HOST-001). 投放消耗/不适用 → 无 Base.
"""
import json, sys

path = sys.argv[1]
rows = json.load(open(path, encoding="utf-8"))
checked = 0
fails = []
for r in rows:
    base_type = r.get("Commission_Base_Type")
    if base_type in (None, ""):
        continue
    base = r.get("Commission_Base")
    ratio = r.get("Commission_Ratio")
    amt = r.get("Commission_Amount")
    expected = None
    if base not in (None, "") and ratio not in (None, ""):
        expected = round(float(base) * float(ratio), 8)
    if expected is None:
        # should be blank
        if amt not in (None, ""):
            fails.append({"Result_ID": r["Result_ID"], "issue": "expected blank but got amount", "amt": amt, "base": base, "ratio": ratio})
    else:
        got = None if amt in (None, "") else round(float(amt), 8)
        checked += 1
        if got is None or abs(got - expected) > 1e-8:
            fails.append({"Result_ID": r["Result_ID"], "issue": "amount mismatch", "expected": expected, "got": amt, "base": base, "ratio": ratio})
print(f"checked {checked} rows with base+ratio")
if fails:
    print("FAILS:", len(fails))
    for f in fails[:20]:
        print(json.dumps(f, ensure_ascii=False))
else:
    print("ALL COMMISSION_AMOUNT MANUAL RECHECK PASSED")
