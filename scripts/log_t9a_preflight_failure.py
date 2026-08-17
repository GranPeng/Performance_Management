#!/usr/bin/env python3
"""Write the T9a failed-preflight batch and its Error_Log rows exactly once."""
import json, subprocess
from datetime import datetime
from pathlib import Path

BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
BATCH_TABLE = "tblHV3JoVR9AEETw"
ERROR_TABLE = "tbl4ZpuuOxZacWgj"
BATCH_ID = "IB-T9A-PREFLIGHT-20260817-01"
SOURCE = "SIMULATED_T9A"

def call(args):
    p = subprocess.run(["lark-cli", "base", *args, "--as", "user"], text=True, capture_output=True)
    obj = json.loads(p.stdout)
    if p.returncode or not obj.get("ok"):
        raise RuntimeError(obj)
    return obj["data"]

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    prior = call(["+record-list", "--base-token", BASE, "--table-id", BATCH_TABLE, "--field-id", "Batch_ID", "--limit", "200", "--format", "json"])
    if BATCH_ID in [row[0] for row in prior["data"]]:
        raise SystemExit("Refusing duplicate failed-preflight batch")
    details = json.loads(Path("data/output/T9a模拟Actual错误日志.json").read_text(encoding="utf-8"))["errors"]
    batch = {"Batch_ID": BATCH_ID, "Batch_Type": "ACTUAL", "Source_Type": "SIMULATED", "Source_File": "T9a模拟Actual清单.json",
             "Import_Time": now, "Operator": "data-engineer/T9a", "Total_Count": 0, "Success_Count": 0, "Fail_Count": len(details),
             "Source": SOURCE, "Create_Time": now, "Update_Time": now, "Status": "Failed"}
    created_batch = call(["+record-batch-create", "--base-token", BASE, "--table-id", BATCH_TABLE, "--json", json.dumps({"create_records": [batch]}, ensure_ascii=False)])
    batch_rid = created_batch["record_id_list"][0]
    rows = []
    for i, err in enumerate(details, 1):
        rows.append({"Error_ID": f"ERR-T9A-PREFLIGHT-{i:03d}", "Batch_ID": [{"id": batch_rid}],
                     "Object_Type": "T9A_PREFLIGHT", "Object_ID": str(err["detail"]), "Error_Type": err["error_type"],
                     "Error_Content": json.dumps(err, ensure_ascii=False), "Process_Status": "待处理", "Source": SOURCE,
                     "Create_Time": now, "Update_Time": now, "Status": "Active"})
    created_errors = call(["+record-batch-create", "--base-token", BASE, "--table-id", ERROR_TABLE, "--json", json.dumps({"create_records": rows}, ensure_ascii=False)])
    result = {"batch_record_id": batch_rid, "batch_id": BATCH_ID, "error_record_ids": created_errors["record_id_list"], "error_count": len(rows)}
    Path("data/output/T9a预检失败写入结果.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__": main()
