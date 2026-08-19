#!/usr/bin/env python3
"""T11c helper: print specific rows by Result_ID for manual commission recheck."""
import json, sys

path = sys.argv[1]
ids = sys.argv[2:]
rows = {r["Result_ID"]: r for r in json.load(open(path, encoding="utf-8"))}
for rid in ids:
    if rid in rows:
        r = rows[rid]
        print(json.dumps({"Result_ID": rid,
                          "Employee_ID": r.get("Employee_ID"),
                          "Metric_ID": r.get("Metric_ID"),
                          "Monthly_Total": r.get("Monthly_Total"),
                          "Auto_Score": r.get("Auto_Score"),
                          "Final_Score": r.get("Final_Score"),
                          "Commission_Base_Type": r.get("Commission_Base_Type"),
                          "Commission_Base": r.get("Commission_Base"),
                          "Commission_Ratio": r.get("Commission_Ratio"),
                          "Commission_Amount": r.get("Commission_Amount")}, ensure_ascii=False))
