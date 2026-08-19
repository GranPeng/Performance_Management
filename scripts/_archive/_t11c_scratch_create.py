#!/usr/bin/env python3
"""T11c helper: create scratch table to validate formula syntax before touching production."""
import json, shutil, subprocess, sys, time
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args, retries=4):
    last = None
    for attempt in range(retries):
        p = subprocess.run([CLI_BIN, "base", *args, "--as", "user"], text=True, capture_output=True)
        try:
            result = json.loads(p.stdout)
        except json.JSONDecodeError:
            last = RuntimeError(f"CLI non-JSON: {p.stdout[-500:]} stderr={p.stderr[-500:]}")
            time.sleep(2); continue
        if p.returncode != 0 or not result.get("ok"):
            last = RuntimeError(json.dumps(result, ensure_ascii=False))
            time.sleep(2); continue
        return result["data"]
    raise last

FIELDS = [
    {"type": "text", "name": "Period"},
    {"type": "link", "name": "Employee_ID", "link_table": "tblc59aB4EnSxkQv"},
    {"type": "link", "name": "Metric_ID", "link_table": "tbldKtdIVv8nnTyX"},
    {"type": "link", "name": "Actual_ID", "link_table": "tbli9VhcUFjVDeNd"},
    {"type": "link", "name": "Project_ID", "link_table": "tbl1GO2vR9ZAqPbr"},
    {"type": "number", "name": "Target_Value_Snapshot"},
    {"type": "formula", "name": "Project_Run_Days",
     "expression": "IF(ISBLANK([Project_ID]),\"\",IF(ISBLANK(FIRST([Project_ID].[Start_Date])),\"\",DAYS(EOMONTH(TODATE([Period]&\"-01\"),0),FIRST([Project_ID].[Start_Date]))))"},
    {"type": "formula", "name": "Is_Exempt", "expression": "IF(ISBLANK([Project_Run_Days]),\"\",[Project_Run_Days]<90)"},
    {"type": "formula", "name": "Test_Commission_Base",
     "expression": "IF(ISBLANK([Employee_ID])||ISBLANK([Period]),\"\",FIRST([Actual].FILTER(CurrentValue.[Employee_ID]=[Employee_ID]&&CurrentValue.[Period]=[Period]&&CONTAIN(CurrentValue.[Metric_ID].[Metric_ID],\"MET-V04-IE-OPS-001\")).SORTBY([Actual].[Actual_Value],FALSE).[Actual_Value]))"},
    {"type": "formula", "name": "Test_Commission_Ratio",
     "expression": "IF(ISBLANK([Test_Commission_Base]),\"\",IF(ISBLANK(FIRST([Actual].FILTER(CurrentValue.[Employee_ID]=[Employee_ID]&&CurrentValue.[Period]=[Period]&&CONTAIN(CurrentValue.[Metric_ID].[Metric_ID],\"MET-V04-IE-OPS-001\")).SORTBY([Actual].[Actual_Value],FALSE).[Actual_Value])),\"\",0.003))"},
    {"type": "formula", "name": "Test_Amount", "expression": "IFBLANK([Test_Commission_Base],0)*IFBLANK([Test_Commission_Ratio],0)"},
    {"type": "formula", "name": "Test_Auto_Exempt",
     "expression": "IF([Is_Exempt]=TRUE(),100,\"regular\")"},
]

def main():
    r = cli(["+table-create", "--base-token", BASE, "--name", "T11C_scratch",
             "--fields", json.dumps(FIELDS, ensure_ascii=False)])
    t = r.get("table", {})
    print(json.dumps({"table_id": t.get("table_id") or t.get("id"), "name": t.get("name"),
                      "full": r}, ensure_ascii=False)[:2000])

if __name__ == "__main__":
    main()
