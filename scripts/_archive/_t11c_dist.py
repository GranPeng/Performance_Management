#!/usr/bin/env python3
"""T11c helper: count commission snapshot fields distribution."""
import json, sys
from collections import Counter

path = sys.argv[1]
rows = json.load(open(path, encoding="utf-8"))
print("rows:", len(rows))
for f in ["Commission_Base_Type", "Commission_Base", "Commission_Ratio", "Commission_Amount"]:
    nonnull = [r[f] for r in rows if r.get(f) not in (None, "")]
    print(f"{f}: non-null={len(nonnull)}")
    if f == "Commission_Base_Type":
        print("  types:", dict(Counter(str(x) for x in nonnull)))
    elif nonnull:
        print("  sample:", nonnull[:5])
