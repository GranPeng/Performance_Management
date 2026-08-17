#!/usr/bin/env python3
"""回滚 T8c 的记录级归并变更；不删除 D-012 已批准的 14 个 Note 字段。默认干跑，--apply 才写 Base。"""
from __future__ import annotations
import argparse, json, os, subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/output"
BASE = "FCxObLU6yao5jgsciZfcWHKwnjh"
TABLES = {"Position": "tbldzvsg9Op6pK29", "Employee": "tblc59aB4EnSxkQv", "Error_Log": "tbl4ZpuuOxZacWgj", "Import_Batch": "tblHV3JoVR9AEETw"}
RESULT = OUT / "T8c_position_merge_execution_result.json"


def cli(args, payload=None):
    cmd = ["lark-cli", "base", *args, "--as", "user", "--format", "json"]
    if payload is not None:
        path = OUT / "t8c_payloads" / "rollback.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
        cmd += ["--json", "@" + str(path.relative_to(ROOT))]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=os.environ | {"LARKSUITE_CLI_NO_UPDATE_NOTIFIER":"1", "LARKSUITE_CLI_NO_SKILLS_NOTIFIER":"1"})
    body = json.loads(result.stdout) if result.stdout else {"ok": False, "stderr": result.stderr}
    if result.returncode or not body.get("ok"):
        raise RuntimeError(json.dumps({"rc":result.returncode,"body":body,"stderr":result.stderr}, ensure_ascii=False))
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not RESULT.exists():
        raise RuntimeError(f"缺少执行清单：{RESULT}")
    data = json.loads(RESULT.read_text(encoding="utf-8"))
    plan = data["plan"]
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    updates = {}
    for table in ("Employee", "Position", "Error_Log"):
        updates[table] = {item["record_id"]: {**item["prior"], "Update_Time": stamp} for item in plan["updates"][table]}
    manifest = {"task":"T8c-rollback", "decision":"仅回滚T8c记录级归并；D-012 Note字段保留", "generated_at":stamp, "source_execution_result":str(RESULT), "updates":updates, "scope":"Employee.Position_ID、Position.Status/Note、Error_Log 状态；不删除正式模型 Note 字段，不修改 Metric/Target/业务结果"}
    path = OUT / "T8c_position_merge_rollback_plan.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.apply:
        print(json.dumps({"status":"DRY_RUN", "plan":str(path), "record_counts":{k:len(v) for k,v in updates.items()}}, ensure_ascii=False))
        return
    for table, records in updates.items():
        response = cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLES[table]], {"update_records": records})
        if response.get("data",{}).get("ignored_fields"):
            raise RuntimeError(f"{table} 回滚有 ignored_fields: {response['data']['ignored_fields']}")
    print(json.dumps({"status":"ROLLBACK_COMPLETED", "plan":str(path)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
