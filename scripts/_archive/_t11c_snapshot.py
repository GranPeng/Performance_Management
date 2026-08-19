#!/usr/bin/env python3
"""T11c helper: snapshot key fields of Performance_Result before/after runs."""
import json, shutil, subprocess, sys, time
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = "tbl6tFtVKExFUTWo"
CLI_BIN = shutil.which("lark-cli") or str(Path.home() / ".local/bin/lark-cli")

def cli(args, retries=5):
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

FIELDS = ["Result_ID", "Period", "Employee_ID", "Metric_ID", "Monthly_Total",
          "Auto_Score", "Final_Score", "Weighted_Score", "Is_Exempt",
          "Commission_Base_Type", "Commission_Base", "Commission_Ratio", "Commission_Amount"]

def main():
    out = []
    offset = 0
    while True:
        args = ["+record-list", "--base-token", BASE, "--table-id", TABLE, "--limit", "200", "--format", "json"]
        for f in FIELDS:
            args += ["--field-id", f]
        if offset:
            args += ["--offset", str(offset)]
        data = cli(args)
        names = data["fields"]
        ids = data["record_id_list"]
        for rid, values in zip(ids, data["data"]):
            row = dict(zip(names, values)); row["_record_id"] = rid
            out.append({k: row.get(k) for k in ["Result_ID", "Employee_ID", "Metric_ID", "Monthly_Total", "Auto_Score", "Final_Score", "Weighted_Score", "Is_Exempt", "Commission_Base_Type", "Commission_Base", "Commission_Ratio", "Commission_Amount"]})
        if not data.get("has_more"):
            break
        offset += len(ids)
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
