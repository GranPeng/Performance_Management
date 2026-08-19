#!/usr/bin/env python3
"""T11c helper: summarize snapshot json."""
import json, sys
from collections import Counter

path = sys.argv[1]
rows = json.load(open(path, encoding="utf-8"))
print("rows:", len(rows))
mt = [r["Monthly_Total"] for r in rows]
print("Monthly_Total non-null:", sum(1 for x in mt if x not in (None, "")), "/", len(mt))
print("Monthly_Total values:", dict(Counter(str(round(float(x), 4)) for x in mt if x not in (None, ""))))
print("Commission_Amount non-null:", sum(1 for r in rows if r["Commission_Amount"] not in (None, "")))
print("Is_Exempt non-null:", sum(1 for r in rows if r["Is_Exempt"] not in (None, "")))
print("Commission_Base_Type non-null:", sum(1 for r in rows if r.get("Commission_Base_Type") not in (None, "")))
print("sample:", json.dumps(rows[:3], ensure_ascii=False))
