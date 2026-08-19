#!/usr/bin/env python3
"""T11c helper: insert scratch test rows and read back formula results."""
import json, shutil, subprocess, sys, time
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLE = "tblpe7iEF8E6DcLz"
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

# 运营岗员工 ACT000001: EMP=recvslsi1WDDZI, Metric=recvsgqAO9P9uR (SUP-001), value=300.5377, Period=2026-07
ROWS = [
    {"Period": "2026-07", "Employee_ID": [{"id": "recvslsi1WDDZI"}],
     "Metric_ID": [{"id": "recvsgqAO9P9uR"}], "Actual_ID": [{"id": "recvswHlTAP6Yi"}]},
    # 带项目（高个子 PROJ000003 recvslrVCv0oRY；无 Start_Date → Is_Exempt 空）
    {"Period": "2026-07", "Employee_ID": [{"id": "recvslsi1WnfMU"}],
     "Metric_ID": [{"id": "recvsgqAO9sss4"}], "Actual_ID": [{"id": "recvswHlTB0MK1"}],
     "Project_ID": [{"id": "recvslrVCv0oRY"}]},
]

def main():
    r = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE,
             "--json", json.dumps({"create_records": ROWS}, ensure_ascii=False)])
    print("created:", json.dumps(r, ensure_ascii=False)[:500])
    # read back formula fields
    fields = ["Period", "Employee_ID", "Metric_ID", "Project_ID", "Project_Run_Days", "Is_Exempt",
              "Test_Commission_Base", "Test_Commission_Ratio", "Test_Amount", "Test_Auto_Exempt"]
    d = cli(["+record-list", "--base-token", BASE, "--table-id", TABLE, "--limit", "200", "--format", "json"]
            + [a for f in fields for a in ("--field-id", f)])
    names = d["fields"]; ids = d["record_id_list"]
    for rid, values in zip(ids, d["data"]):
        row = dict(zip(names, values))
        print(json.dumps({"_id": rid, **{k: row.get(k) for k in fields}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
