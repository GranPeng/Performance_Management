#!/usr/bin/env python3
"""T11c helper: build scratch table to validate exemption branch formulas.

Fields mirror Production Performance_Result exemption chain:
  Period, Project_Run_Days(number), Is_Exempt(formula <90),
  Auto_Score(exempt: IF Is_Exempt -> 100 else "regular"),
  Weighted_Score(exempt: IF Is_Exempt -> 0 else weight*final),
  Monthly_Total(SUM same-table Weighted_Score by EMP+Period)
Insert 2 rows: run_days=60 (exempt) and run_days=120 (not exempt).
"""
import json, shutil, subprocess, sys, time
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args, retries=5):
    last = None
    for attempt in range(retries):
        p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
        try:
            result = json.loads(p.stdout)
        except json.JSONDecodeError:
            last = RuntimeError(f"CLI non-JSON: {p.stdout[-500:]}")
            time.sleep(2); continue
        if p.returncode != 0 or not result.get("ok"):
            last = RuntimeError(json.dumps(result, ensure_ascii=False))
            time.sleep(2); continue
        return result["data"]
    raise last

FIELDS = [
    {"type": "text", "name": "Period"},
    {"type": "number", "name": "Project_Run_Days"},
    {"type": "number", "name": "Weight"},
    {"type": "number", "name": "Final_Score"},
    {"type": "formula", "name": "Is_Exempt", "expression": "IF(ISBLANK([Project_Run_Days]),\"\",[Project_Run_Days]<90)"},
    {"type": "formula", "name": "Auto_Score",
     "expression": "IF([Is_Exempt]=TRUE(),100,\"regular\")"},
    {"type": "formula", "name": "Weighted_Score",
     "expression": "IF([Is_Exempt]=TRUE(),0,IFBLANK([Weight],0)*IFBLANK([Final_Score],0))"},
    {"type": "formula", "name": "Monthly_Total",
     "expression": "SUM([T11C_scratch_exempt].FILTER(CurrentValue.[Period]=[Period]).[Weighted_Score].LISTCOMBINE())"},
]

def main():
    # delete leftover if any
    try:
        d = cli(["+table-list", "--base-token", BASE])
        for t in d["tables"]:
            if t["name"] == "T11C_scratch_exempt":
                cli(["+table-delete", "--base-token", BASE, "--table-id", t["id"], "--yes"])
    except Exception as e:
        print("cleanup:", e)
    r = cli(["+table-create", "--base-token", BASE, "--name", "T11C_scratch_exempt",
             "--fields", json.dumps(FIELDS, ensure_ascii=False)])
    t = r.get("table", {})
    tid = t.get("table_id") or t.get("id")
    print("scratch table:", tid)

    rows = [
        {"Period": "2026-07", "Project_Run_Days": 60, "Weight": 0.3, "Final_Score": 42},  # exempt
        {"Period": "2026-07", "Project_Run_Days": 120, "Weight": 0.3, "Final_Score": 80},  # not exempt
    ]
    c = cli(["+record-batch-create", "--base-token", BASE, "--table-id", tid,
             "--json", json.dumps({"create_records": rows}, ensure_ascii=False)])
    time.sleep(3)
    d = cli(["+record-list", "--base-token", BASE, "--table-id", tid, "--limit", "200", "--format", "json"]
            + [a for f in ["Period", "Project_Run_Days", "Is_Exempt", "Auto_Score", "Weighted_Score", "Monthly_Total"] for a in ("--field-id", f)])
    names = d["fields"]; ids = d["record_id_list"]
    for rid, vals in zip(ids, d["data"]):
        row = dict(zip(names, vals))
        print(json.dumps({"_id": rid, "run_days": row.get("Project_Run_Days"), "Is_Exempt": row.get("Is_Exempt"),
                          "Auto_Score": row.get("Auto_Score"), "Weighted_Score": row.get("Weighted_Score"),
                          "Monthly_Total": row.get("Monthly_Total")}, ensure_ascii=False))
    # cleanup
    cli(["+table-delete", "--base-token", BASE, "--table-id", tid, "--yes"])
    print("scratch cleaned")

if __name__ == "__main__":
    main()
