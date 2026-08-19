#!/usr/bin/env python3
"""T11c helper: find RST ids for a given metric (first few)."""
import json, sys

path = sys.argv[1]
metric = sys.argv[2]
rows = json.load(open(path, encoding="utf-8"))
cnt = 0
for r in rows:
    if r.get("Metric_ID") == metric:
        print(r["Result_ID"])
        cnt += 1
        if cnt >= 8:
            break
